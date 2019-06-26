import json
import os
import random
import string
import re
from io import BytesIO

import requests
import xmltodict
import time
import jwt
import logging
import qiniu
from PIL import Image

from django.db import transaction, connection
from django.db.models import Max, Min
from django.db.models import OuterRef
from django.db.models import Subquery
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta

from lib.get_qrcode import sharePoster
from lib.signals import signal_first_visit, signal_first_order, signal_pay
from apscheduler.scheduler import Scheduler
from pymysql import *

from django.views import View
from django.views.decorators.csrf import csrf_exempt

from lib import model_2_dict, gen_resp, Code, check_data_must, gen_order_no, gen_trade_no, wx_sign, wx_reply

from main.models import *
from plugin.invite.models import UidFee, CashOut
from shop import settings
from shop.settings import ORDER_PAGE_NUM, NOTI_URL, QINIU_ACCESS_KEY, QINIU_SECRET_KEY, QINIU_BUCKET_NAME, HOST_URL
from shop.settings import DATABASES

log = logging.getLogger()


def index(request):
    # print('code:', type(Code.SUCCESS), Code.SUCCESS)

    user = User.objects.first()
    token = jwt.encode({
        'exp': int((timezone.now() + timedelta(days=30)).timestamp()),
        'appid': user.appid,
        'userid': user.id,
        'from': 'min',
    }, user.apikey, algorithm='HS256')
    return gen_resp(token=token.decode())


# def login(request):
#     """
#     小程序不需要注册步骤，用openid换token
#     :param request:
#     :return:
#     """
#
#     openid = request.POST.get('openid')
#     appid = request.POST.get('appid')
#
#     user = User.objects.filter(appid=appid, openid=openid).first()
#
#     if not user:
#         return gen_resp(code=11, msg='用户不存在')
#
#     token = jwt.encode({
#         'exp': int((timezone.now() + timedelta(days=30)).timestamp()),
#         'appid': user.appid,
#         'openid': user.openid,
#         'from': 'min',
#     }, user.apikey, algorithm='HS256')
#
#     return gen_resp(token=token.decode())


def refresh_token(request):
    """
    更新token接口
    :param request:
    :return:
    """
    pass


def tes(request):
    user: User = request.user
    u2 = User.objects.first()

    log.info(user)
    log.info(u2)
    return gen_resp(user1=model_2_dict(user), user2=model_2_dict(u2))


def getOpenid(request):
    """
    获取用户openid
    :param requst:
    :return:
    """
    code = request.GET.get('code', None)
    appid = request.APPID
    if code is None:
        return gen_resp(20001, msg="参数code为空")
    if appid is None:
        return gen_resp(20001, msg="参数appid为空")
    shop = Shop.objects.filter(appid=appid).first()
    if not shop:
        return gen_resp(20001, msg="appid为{}的商户不存在".format(appid))

    try:
        res = requests.get('https://api.weixin.qq.com/sns/jscode2session', params={
            "appid": appid,
            "secret": shop.secret,
            "js_code": code,
            "grant_type": "authorization_code"
        })
        data = json.loads(res.content.decode())

    except Exception as err:
        log.error("获取openid微信返回数据异常{}".format(err))
        return gen_resp(10000, msg="微信返回数据异常")

    openid = data.get('openid', None)
    if openid is None:
        return gen_resp(10010, msg='wx_err:{}'.format(data.get('errcode')))

    user = User.objects.filter(openid=openid).first()
    if user:
        token = jwt.encode({
            'exp': int((timezone.now() + timedelta(days=30)).timestamp()),
            'uid': user.id,
            'from': 'min',
        }, user.apikey, algorithm='HS256')
        return gen_resp(0, token=token.decode(), openid=openid)
    else:
        return gen_resp(0, openid=openid)


# 创建用户
def login(request):
    appid = request.APPID
    data, rsp = check_data_must(request, ['name', 'openid'])
    if rsp:
        return rsp
    log.info(data)
    openid = data.get('openid')
    markId = data.get('markId')
    shareBy = data.get('shareBy')
    if User.objects.filter(openid=openid).exists():
        return gen_resp(20003, msg="用户已存在")
    try:  # 创建用户

        user = User()
        user.name = data.get('name')
        user.avatar = data.get('avatar')
        user.openid = data.get('openid')
        user.phone = data.get('phone')
        user.birth = data.get('birth')
        user.sex = 0 if data.get('sex') == 2 else data.get('sex')
        user.appid = appid
        user.save()
        token = jwt.encode({
            'exp': int((timezone.now() + timedelta(days=30)).timestamp()),
            'uid': user.id,
            'from': 'min',
        }, user.apikey, algorithm='HS256')
        log.info("-------signal--------")
        signal_first_visit.send(sender=None, appid=appid, markId=markId, shareBy=shareBy, userId=user.id)
        log.info('end---------signal')
        return gen_resp(0, msg="创建用户成功", token=token.decode())
    except Exception as err:
        log.error('用户{}创建失败{}'.format(openid, err))
        return gen_resp(10000, msg="创建用户失败")


class UserView(View):

    # 获取用户信息
    def get(self, request):
        """
        获取用户信息
        :param request:
        :return:
        """
        user: User = request.user
        if not user:
            return gen_resp(20004, msg="用户不存在")
        else:
            user = model_2_dict(user, fields=['name', 'phone', 'avatar'])
        return gen_resp(0, user=user)

    def post(self, request):
        """
        修改用户信息
        :param request:
        :return:
        """

        user: User = request.user
        data = json.loads(request.body)
        user = User.objects.filter(id=user.id).first()
        if not user:
            return gen_resp(20004, msg="userid为{}的用户不存在".format(user.id))

        user.name = data.get('name') or user.name
        user.avatar = data.get('avatar') or user.avatar
        user.phone = data.get('phone') or user.phone
        user.birth = data.get('birth') or user.birth
        user.sex = data.get('sex') or user.sex
        try:
            user.save()
            return gen_resp(0, msg="修改用户信息成功")
        except Exception as err:
            log.error('用户{}修改失败{}'.format(data.get('openid'), err))
            return gen_resp(10000, msg="修改用户信息失败")


# 商城轮播图
def homeImg(request):
    user: User = request.user
    homeImgs = HomeImg.objects.filter(appid=user.appid)
    imgList = [model_2_dict(itm, fields=['image', 'imgType', 'idpath']) for itm in homeImgs]
    return gen_resp(0, imgList=imgList)


# 首页tag
def homeTag(request):
    user: User = request.user
    tagId = request.GET.get('id')
    if not tagId:
        tagList = list(Tag.objects.filter(appid=user.appid).values('id', 'name'))
        return gen_resp(0, tagList=tagList)
    else:
        if not str(tagId).isdigit():
            return gen_resp(20001, msg="tagId参数类型错误")

        page = request.GET.get('page', '1')
        if not str(page).isdigit() or page == '0':
            page = 1
        else:
            page = int(page)

        spuIdList = SpuTag.objects.filter(tagId=tagId).values_list('spuId', flat=True)
        spuList = []
        spu_cnt = Spu.objects.filter(id__in=spuIdList, state=1).count()
        spus = Spu.objects.filter(id__in=spuIdList, state=1).annotate(
            min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
            max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
        ).order_by('-created')[
               (page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]

        for spu in spus:
            spuDic = model_2_dict(spu, fields=['id', 'title', 'cover'])
            price = str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else str(spu.min_price)
            spuDic['price'] = price
            spuList.append(spuDic)
    return gen_resp(0, spuList=spuList,
                    more=page < spu_cnt / ORDER_PAGE_NUM
                    )


# 首页导航
def homeCate(request):
    user: User = request.user
    cateIdList = HomeCate.objects.filter(appid=user.appid).order_by('index').values_list('cateId', flat=True)
    cates = Cate.objects.filter(id__in=cateIdList)
    cateList = [model_2_dict(itm, fields=['id', 'name', 'cover']) for itm in cates]
    return gen_resp(0, cateList=cateList)


# 搜索商品
def search(request):
    keyword = request.GET.get('keyword')
    if not keyword:
        return gen_resp(20001, msg="搜索关键字为空")
    page = request.GET.get('page', '1')
    if not str(page).isdigit() or page == '0':
        page = 1
    else:
        page = int(page)
    spu_cnt = Spu.objects.filter(title__contains=keyword, state=1).count()
    spus = Spu.objects.filter(title__contains=keyword, state=1).annotate(
        min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
        max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
    )[
           (page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
    spuList = []
    for spu in spus:
        # 商品id 商品名称 价格 商品图片  ！！上架中商品
        spuDic = model_2_dict(spu, fields=['id', 'title', 'cover'])
        price = str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else str(spu.min_price)
        spuDic['price'] = price
        spuList.append(spuDic)

    more = page < spu_cnt / ORDER_PAGE_NUM
    return gen_resp(0, spuList=spuList, more=more)


# 获取分类/商品
def cate(request):
    user: User = request.user
    cateId = request.GET.get('id')
    cateList = list(Cate.objects.filter(appid=user.appid, pid=0).values('id', 'name'))
    if not cateId:
        return gen_resp(0, cateList=cateList)
    else:
        if not str(cateId).isdigit():
            return gen_resp(20001, msg="cateId参数类型错误")
        cate2 = Cate.objects.filter(pid=cateId)
        spuList = []
        if cate2:
            cateList = [model_2_dict(itm, fields=['id', 'name', 'cover']) for itm in cate2]
            return gen_resp(0, cateList=cateList)
        else:
            page = request.GET.get('page', '1')
            if not str(page).isdigit() or page == '0':
                page = 1
            else:
                page = int(page)
            spu_cnt = Spu.objects.filter(cateId=cateId, state=1).count()
            spus = Spu.objects.filter(cateId=cateId, state=1).annotate(
                min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
                max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
            ).order_by('-created')[(page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
            for spu in spus:
                spuDic = model_2_dict(spu, fields=['id', 'title', 'cover'])
                price = str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else str(spu.min_price)
                spuDic['price'] = price
                spuList.append(spuDic)

            more = page < spu_cnt / ORDER_PAGE_NUM
            return gen_resp(0, spuList=spuList, more=more)


# 猜你喜欢
def related(request):
    """
    随机返回6个商品
    :param request:
    :return:
    """
    appid = request.APPID
    spus = Spu.objects.filter(appid=appid, state=1).annotate(
        min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
        max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
    ).order_by('?')[:6]
    spuList = []
    for spu in spus:
        spuDic = model_2_dict(spu, fields=['id', 'title', 'cover'])
        price = str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else str(spu.min_price)
        spuDic['price'] = price
        spuList.append(spuDic)

    return gen_resp(0, spuList=spuList)


# 商品详情
def spuDetail(request):
    user: User = request.user
    spuId = request.GET.get('id')
    if spuId is None or not str(spuId).isdigit():
        return gen_resp(Code.PARAM_ERROR, msg="spuId为空或参数类型错误")

    spu = Spu.objects.filter(id=spuId, state=1).annotate(
        min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
        max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
    ).first()

    if not spu:
        return gen_resp({
            "code": 20004,
            "msg": "spuId为{}的商品不存在".format(spuId)
        })

    spuDic = model_2_dict(spu, fields=['id', 'title', 'video', 'sales', 'shipId', 'state'])
    imgs = SpuImg.objects.filter(spuId=spuId)
    imgList = [itm.image.url for itm in imgs]
    spuDic['imgList'] = imgList

    # 价格
    price = str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else str(spu.min_price)
    spuDic['price'] = price

    # 保障服务
    spuServ = list(SpuServ.objects.filter(spuId=spuId).values_list('serv', flat=True))
    spuDic['servList'] = spuServ

    # 评论标签
    cur = connection.cursor()
    cur.execute(
        'select distinct tc.name from jkb_tag_cmt tc inner join '
        'jkb_spu_cmt_tag sct on tc.id = sct.tagCmtId inner join '
        'jkb_spu_cmt sc on sct.spuCmtId = sc.id where sc.spuId = %s '
        'group by tc.name order by count(tc.name) desc',
        (spuId,))

    tagList = [itm[0] for itm in cur.fetchall()]
    spuDic['tagList'] = tagList[0:3] if len(tagList) > 3 else tagList

    # 评价内容
    cur.execute(
        'select sc.content, sc.created, u.name, u.avatar from '
        'jkb_spu_cmt sc, jkb_user u where sc.spuId = %s and u.id = sc.UserId',
        (spuId,))
    cmtList = [{'content': itm[0], 'created': int(itm[1].timestamp()), 'name': itm[2], 'avatar': itm[3]} for itm in
               cur.fetchall()]
    spuDic['cmtList'] = cmtList[0] if len(cmtList) > 1 else cmtList

    # 是否收藏
    favor = Favor.objects.filter(objId=spuId, userId=user.id).first()
    spuDic['isFavor'] = 1 if favor else 0

    # 图文详情
    conts = SpuContent.objects.filter(spuId=spuId).order_by('id')
    contList = [model_2_dict(itm, fields=['image', 'video', 'text']) for itm in conts]
    spuDic['contList'] = contList

    skus = Sku.objects.filter(spuId=spuId)
    skuList = []
    stock = 0
    for itm in skus:
        tmp = model_2_dict(itm, fields=['price', 'stock', 'cover'])
        cur.execute(
            'select n.name, v.value from jkb_attr_value v left join jkb_attr_name n '
            'on v.attId=n.id where v.skuId=%s order by v.attId',
            (itm.id,))
        tmp['attrs'] = [{itm[0]: itm[1]} for itm in cur.fetchall()]
        tmp['skuId'] = itm.id
        stock += itm.stock
        skuList.append(tmp)
    # 总库存
    spuDic['stock'] = stock
    spuDic['skuList'] = skuList
    cur.close()
    connection.close()
    return gen_resp(0, spuDic=spuDic)


class SpuCmtView(View):
    """
    评论列表 详情
    """

    def get(self, request):
        spuId = request.GET.get('id')
        tagId = request.GET.get('tagId')
        cmtId = request.GET.get('cmtId')

        tagList = []
        more = ''
        if cmtId:
            # 获取评论详情
            if not str(cmtId).isdigit():
                return gen_resp(20001, msg="cmtId参数类型错误")
            spuCmts = SpuCmt.objects.filter(id=cmtId, status=1)
        else:
            if not str(spuId).isdigit():
                return gen_resp(20001, '参数spuId格式不正确')
            page = request.GET.get('page', '1')
            if not str(page).isdigit() or page == '0':
                page = 1
            else:
                page = int(page)
            if not tagId:
                # 获取所有(评论标签和评论） 先获取标签  再获取评论
                with connection.cursor() as cur:
                    cur.execute(
                        'select tc.* from jkb_tag_cmt tc '
                        'inner join jkb_spu_cmt_tag sct on tc.id = sct.tagCmtId '
                        'inner join jkb_spu_cmt sc on sct.spuCmtId = sc.id where sc.spuId = %s group by tc.name',
                        (spuId,))
                    tagList = [{'id': itm[0], 'name': itm[1], 'cnt': itm[2]} for itm in cur.fetchall()]
                cmtConts = SpuCmt.objects.filter(spuId=spuId, status=1)
                # 获取所有评论
                cmt_cnt = cmtConts.count()
                spuCmts = cmtConts.order_by('-created')[(page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
                more = page < cmt_cnt / ORDER_PAGE_NUM
            else:
                # 获取对应tag下的所有评论
                if not str(tagId).isdigit():
                    return gen_resp(20001, msg="tagId参数类型错误")
                spuCmtIdList = SpuCmtTag.objects.filter(tagCmtId=tagId).values_list('spuCmtId', flat=True)
                cmt_cnt = SpuCmt.objects.filter(id__in=spuCmtIdList, status=1).count()
                spuCmts = SpuCmt.objects.filter(id__in=spuCmtIdList, status=1).order_by('-created')[(page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
                more = page < cmt_cnt / ORDER_PAGE_NUM

        cmtList = []
        for itm in spuCmts:
            user = User.objects.filter(id=itm.userId).first()
            tmp = model_2_dict(itm, fields=['content', 'created'])
            tmp['name'] = user.name
            tmp['avatar'] = user.avatar
            cmtImgs = CmtImg.objects.filter(spuCmtId=itm.id)
            tmp['imgList'] = [itm.image.url for itm in cmtImgs]
            if itm.replyTo:
                reCmt = SpuCmt.objects.filter(id=itm.replyTo, status=1).first()
                tmp['replyCont'] = reCmt.content
            else:
                tmp['replyCont'] = ''
            if not cmtId:
                tmp['cmtId'] = itm.id  # 商品评论id
            cmtList.append(tmp)
        if tagId:
            return gen_resp(0, cmtList=cmtList, more=more)
        elif cmtId:
            return gen_resp(0, cmt=cmtList[0])
        else:
            return gen_resp(0, tagList=tagList, cmtList=cmtList, more=more)
            # 只传spuId获取全部评价
            # 传spuId、标签id获取某个标签下的所有评价
            # cmtId 查看单个评价

    def post(self, request):
        user = request.user
        data, rsp = check_data_must(request, must=['orderId', 'skuId', 'userType', 'content'])
        if rsp:
            return rsp

        orderId = data.get('orderId')
        # spuId = data.get('spuId')
        skuId = data.get('skuId')
        userType = data.get('userType')
        content = data.get('content')

        cmtImg = data.get('cmtImg')
        tagCmtList = data.get('tagCmtList')
        if tagCmtList:
            if not isinstance(tagCmtList, list) or len(tagCmtList) == 0:
                return gen_resp(20001, 'tagCmtList参数不符合格式或为空')
            for item in tagCmtList:
                if not isinstance(item, int):
                    return gen_resp(20001, 'tagCmtList内部参数不是int')
        sku = Sku.objects.filter(id=skuId).first()
        if not sku:
            return gen_resp(20004, '此sku不存在')
        spuId = sku.spuId

        order = Order.objects.filter(id=orderId, userId=user.id).first()
        if not order:
            return gen_resp(20004, '订单不存在')

        if order.status != 3:
            return gen_resp(10001, '不是待评价订单')

        # 校验sku 是否在orderSku里面
        if not OrderSku.objects.filter(orderId=orderId, skuId=skuId).exists():
            return gen_resp(10001, '此sku不在orderSku里面')

        spu = Spu.objects.filter(id=spuId).first()
        if not spu:
            return gen_resp(20004, 'spu不存在')

        if userType not in [0, 1]:
            return gen_resp(20001, 'userType类型超出范围')

        if cmtImg:
            if not isinstance(cmtImg, list) or len(cmtImg) == 0:
                return gen_resp(20001, 'cmtImg参数不符合格式或为空')
        try:
            with transaction.atomic():
                # 订单改变到已评论
                order.isComment = 1
                order.save()
                # 创建 商品评论
                spu_cmt = SpuCmt.objects.create(
                    appid=user.appid,
                    userId=user.id,
                    userType=userType,
                    spuId=spuId,
                    orderId=orderId,
                    content=content,
                    status=1
                )
                # spu总评论加1
                spu.cmtCnt += 1
                spu.save()

                if cmtImg:
                    for item in cmtImg:
                        CmtImg.objects.create(
                            appid=user.appid,
                            image=item,
                            spuCmtId=spu_cmt.id
                        )
                if tagCmtList:
                    for item in tagCmtList:
                        tag_cmt = TagCmt.objects.filter(id=item).first()
                        if not tag_cmt:
                            return gen_resp(20004, '此评价标签不存在')
                        # 标签评论数加1
                        tag_cmt.cnt += 1
                        tag_cmt.save()
                        # 创建评论标签关联表的数据
                        SpuCmtTag.objects.create(
                            appid=user.appid,
                            spuCmtId=spu_cmt.id,
                            tagCmtId=tag_cmt.id
                        )
        except Exception as e:
            log.error('添加评论出错:' + str(e))
            return gen_resp(10000, '添加评论出错')

        return gen_resp(0, '评论成功!')


class CartView(View):
    """
    获取购物车列表
    """
    def get(self, request):
        user: User = request.user
        cartSkus = Cart.objects.filter(userId=user.id)
        cartList = []
        for itm in cartSkus:
            sku = Sku.objects.filter(id=itm.skuId).first()
            skuDic = model_2_dict(sku, fields=['cover', 'price', 'buyMax', 'stock'])
            skuDic['skuId'] = itm.skuId
            skuDic['id'] = itm.id
            skuDic['amount'] = itm.amount
            spu = Spu.objects.filter(id=sku.spuId).first()
            skuDic['spuId'] = spu.id
            skuDic['title'] = spu.title
            skuDic['state'] = spu.state
            specList = list(AttrValue.objects.filter(skuId=itm.skuId).order_by('attId').values_list('value', flat=True))
            skuDic['specList'] = specList
            cartList.append(skuDic)
        return gen_resp(0, cartList=cartList)

    """
    添加修改购物车
    """

    def post(self, request):
        user: User = request.user
        data, rsp = check_data_must(request, ['amount'])
        if rsp:
            return rsp
        skuId = data.get('skuId')
        cartId = data.get('cartId')

        if not (skuId or cartId):
            return gen_resp(20000, msg="skuId或者cartId参数为空")

        amount = data.get('amount')
        if not str(amount).isdigit() or int(amount) < 1:
            return gen_resp(20001, msg="amount参数类型错误")

        if not cartId:
            if not str(skuId).isdigit():
                return gen_resp(20001, msg="skuId参数类型错误")

            cartSku = Cart.objects.filter(userId=user.id, skuId=skuId).first()
            if cartSku:
                cartSku.amount = cartSku.amount + amount
                cartSku.save()
            else:
                Cart.objects.create(userId=user.id, skuId=skuId, amount=amount, appid=user.appid)

            return gen_resp(0, msg='skuId为{}的商品添加购物车成功'.format(skuId))
        else:
            if not str(cartId).isdigit():
                return gen_resp(20001, msg="cartId参数类型错误")
            cartSku = Cart.objects.filter(id=cartId).first()
            if not cartSku:
                return gen_resp(
                    20004,
                    msg="cartId为{}的购物车商品找不到".format(cartId)
                )

            cartSku.amount = amount
            cartSku.save()
            return gen_resp(
                0,
                msg="修改购物车商品数量成功"
            )

    """
    删除购物车商品
    """

    def delete(self, request):
        data = json.loads(request.body)
        cartId = data.get('cartId')
        if not cartId or not str(cartId).isdigit():
            return gen_resp(20001, msg="cartId为空或参数类型错误")
        if not Cart.objects.filter(id=cartId).exists():
            return gen_resp(
                20004,
                msg="cartId为{}的购物车商品找不到".format(cartId)
            )
        try:
            Cart.objects.filter(id=cartId).delete()
            return gen_resp(
                0,
                msg="删除购物车商品成功"
            )
        except Exception as err:
            log.error("购物车商品{}删除失败{}".format(cartId, err))
            return gen_resp(10000, msg="购物车商品删除失败")


# 生成二维码token
def AccessToken(request):
    appid = request.APPID
    shop = Shop.objects.filter(appid=appid).first()
    if not shop:
        return gen_resp(20001, msg="appid为{}的商户不存在".format(appid))
    url = "https://api.weixin.qq.com/cgi-bin/token"
    data = {
        "appid": appid,
        "secret": shop.secret,
        "grant_type": "client_credential"
    }
    try:
        res = requests.get(url, data)
        access_token = res.json().get('access_token')
        return gen_resp(0, access_token=access_token)
    except Exception as err:
        log.error('微信返回access_token处理错误:' + str(err))
        return gen_resp(10000, msg='获取access_token失败')


# 获取分享数据
def shareData(request):
    """
    获取分享数据  shareBy markId
    :param request:
    :return:
    """
    user: User = request.user
    appid = request.APPID
    mark = ShareMark()
    mark.appid = appid
    mark.markType = 0
    try:
        mark.save()
        return gen_resp(code=0, markId=mark.id, shareBy=user.id)
    except Exception as err:
        log.error('userId为{}的ShareMark创建失败{}:'.format(user.id, err))
        return gen_resp(10000, msg='ShareMark创建失败')


def qrCode(request):
    """
    获取分享二维码
    参数： spuId(非必传)
    """
    user: User = request.user
    appid = request.APPID
    data = request.body
    spuId = ''
    if data:
        spuId = json.loads(request.body).get('spuId')
    if spuId:
        if not Spu.objects.filter(id=spuId, state=1).exists():
            return gen_resp(20001, msg="spuId为{}的商品不存在".format(spuId))

    # spuId = spuId if spuId else 0
    spuId = spuId or 0
    hasCode = ShareQrcode.objects.filter(userId=user.id, spuId=spuId).first()
    if hasCode:
        codeUrl = HOST_URL + '/media/' + str(hasCode.image)
        return gen_resp(0, qrCode=codeUrl)

    shop = Shop.objects.filter(appid=appid).first()
    if not shop:
        return gen_resp(20001, msg="appid为{}的商户不存在".format(appid))
    url = "https://api.weixin.qq.com/cgi-bin/token"
    datat = {
        "appid": appid,
        "secret": shop.secret,
        "grant_type": "client_credential"
    }
    res = requests.get(url, datat).json()
    access_token = res.get('access_token')
    if not access_token:
        return gen_resp(10000, msg='获取access_token失败')

    shareBy = user.id
    # 创建分享标志
    mark = ShareMark()
    mark.appid = appid
    mark.markType = 0 if not spuId else 1
    mark.save()
    markId = mark.id
    log.info('qrcode: shareBy {} spuId {}'.format(shareBy, spuId))

    url1 = "https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={}".format(access_token)
    if spuId:
        data = {
            "scene": str(shareBy) + ',' + str(markId) + ',' + str(spuId)
        }
    else:
        data = {
            "scene": str(shareBy) + ',' + str(markId)
        }
    try:
        rsp = requests.post(url1, json=data)
        if rsp.status_code != 200:
            return gen_resp(10000, msg='二维码获取失败')
    except Exception as err:
        log.error('微信请求生成二维码处理错误{}:'.format(err))
        return gen_resp(10000, msg='微信请求生成二维码处理错误')

    if spuId:
        code_stream = BytesIO(rsp.content)
        codeImg = Image.open(code_stream)

        log.info("用户id" .format(user.id))
        if user.avatar:
            ava = requests.get(user.avatar)
            if ava.status_code != 200:
                return gen_resp(10000, msg='用户头像获取失败')
            ava_stream = BytesIO(ava.content)
            avaImg = Image.open(ava_stream)
        else:
            avaImg = Image.new('RGBA', (70, 70), 'white')

        spu = Spu.objects.filter(id=spuId, state=1).annotate(
            min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
            max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
        ).first()
        spuCov = requests.get(spu.cover.url)
        if spuCov.status_code != 200:
            return gen_resp(10000, msg='商品封面图获取失败')
        spu_stream = BytesIO(spuCov.content)
        spuImg = Image.open(spu_stream)

        cont = SpuContent.objects.filter(spuId=spuId).first()
        detail = cont.text if cont else ''
        # 用户名 商品价格 商品详情 商品图片
        price = '￥' + str(spu.min_price) + '-' + str(spu.max_price) if spu.min_price != spu.max_price else '￥' + str(spu.min_price)
        try:
            poster = sharePoster(user.name, price, detail, avaImg, spuImg, codeImg)
        except Exception as err:
            log.error('生成分享海报失败{}:'.format(err))
            return gen_resp(10000, msg='生成分享海报失败')
        # 图片转字节
        byteData = BytesIO()
        poster.save(byteData, format='JPEG')
        byteData = byteData.getvalue()

        fname = "{}_{}_code.png".format(shareBy, spuId)
    else:
        # 分享店铺直接生成二维码
        fname = "{}_code.png".format(shareBy)
        byteData = rsp.content
    try:
        with open(os.path.join(settings.QRCODE_ROOT, 'hyh', fname), 'wb') as f:
            f.write(byteData)
    except Exception as err:
        log.info('分享图片保存失败{}'.format(err))
        return gen_resp(10000, msg='分享图片保存失败')

    # 创建ShareQrcode记录
    qrCode = ShareQrcode()
    qrCode.image = 'hyh/' + fname
    qrCode.userId = user.id
    qrCode.spuId = spuId if spuId else 0
    try:
        qrCode.save()
        return gen_resp(code=0, qrCode=HOST_URL + '/media/hyh/' + fname, msg='分享二维码保存成功')
    except Exception as err:
        log.error('创建ShareQrcode记录{}:'.format(err))
        return gen_resp(10000, msg='创建ShareQrcode记录')


def count(user, date=None):
    """
    计算总收益，月收益, 以及月份的分组，，
    """
    if not date:
        year = datetime.now().year
        month = datetime.now().month
    else:
        date = date.split('-')
        year = date[0]
        month = date[1]
    cur = connection.cursor()
    cur.execute(
        'select co.rid, co.idx, uf.uid from invite_cash_out co '
        'inner join invite_uid_fee uf on uf.id = co.rid where co.pid = %s',
        (user.id,))
    all = cur.fetchall()
    totalFee = 0
    for itm in all:
        uidfee = UidFee.objects.filter(id=itm[0]).first()
        if itm[1] == 1:
            totalFee += uidfee.fee1
        elif itm[1] == 2:
            totalFee += uidfee.fee2
        else:
            totalFee += uidfee.fee3

    cur.execute(
        'select co.rid, co.idx, u.name, u.avatar from invite_cash_out co '
        'inner join invite_uid_fee uf on uf.id = co.rid inner join jkb_user u '
        'on uf.uid = u.id where co.pid = %s and year(created)=%s and '
        'month(created)=%s order by uf.created desc',
        (user.id, year, month))
    dateAll = cur.fetchall()
    monthFee = 0
    for itm in dateAll:
        uidfee = UidFee.objects.filter(id=itm[0]).first()
        if itm[1] == 1:
            monthFee += uidfee.fee1
        elif itm[1] == 2:
            monthFee += uidfee.fee2
        else:
            monthFee += uidfee.fee3
    print("指定日期所有数据", dateAll)
    cur.close()
    connection.close()
    fee = {}
    fee['totalFee'] = totalFee
    fee['monthFee'] = monthFee
    fee['dateAll'] = dateAll if date else []
    log.info('总收益---' .format(fee))
    return fee


# 我的分享列表
def myShare(request):
    """
    默认显示当前月份的收益（总收益，当前月份总收益）
    传日期的话 显示指定月份收益和账单
    """
    user: User = request.user
    date = request.GET.get('date')
    page = request.GET.get('page', '1')
    if not str(page).isdigit() or page == '0':
        page = 1
    else:
        page = int(page)
    cur = connection.cursor()
    cur.execute(
        'select co.rid, co.idx, u.name, u.avatar from invite_cash_out co '
        'inner join invite_uid_fee uf on uf.id = co.rid inner join jkb_user u '
        'on uf.uid = u.id where co.pid = %s order by uf.created desc',
        (user.id,))
    all = cur.fetchall()
    cur.close()
    connection.close()
    # 调用count 获取总收益 还有月收益
    res = count(user, date=date)
    dateAll = res.get('dateAll')
    if not date:
        cnt = len(all)
        dateList = all[(page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
    else:
        cnt = len(dateAll)
        dateList = dateAll[(page - 1) * ORDER_PAGE_NUM: page * ORDER_PAGE_NUM]
    feeList = []
    for itm in dateList:
        tmp = {}
        uidfee = UidFee.objects.filter(id=itm[0]).first()
        tmp['name'] = itm[2]
        tmp['avatar'] = itm[3]
        if itm[1] == 1:
            tmp['fee'] = uidfee.fee1
        elif itm[1] == 2:
            tmp['fee'] = uidfee.fee2
        else:
            tmp['fee'] = uidfee.fee3
        tmp['created'] = int(uidfee.created.timestamp())
        feeList.append(tmp)
    return gen_resp(0, totalFee=res.get('totalFee'), monthFee=res.get('monthFee'), feeList=feeList,
                    more=page < cnt / ORDER_PAGE_NUM)


# ---------------------------------------------------------------------------------------------------------

"""
# 定时任务，按商家设定的时间未支付则取消

"""


def new_task():
    # 创建Connection连接
    conn = connect(
        host=DATABASES['default']['HOST'],
        port=3306,
        database=DATABASES['default']['NAME'],
        user=DATABASES['default']['USER'],
        password=DATABASES['default']['PASSWORD'],
        charset='utf8')
    try:
        cs1 = conn.cursor()
        # 查询所有待收货订单
        cs1.execute('select o.id, o.created from jkb_order as o where o.status = 2')
        waitOrders = cs1.fetchall()
        # 七天前
        time = datetime.now() + timedelta(days=-7)
        for item in waitOrders:
            orderId = item[0]
            created = item[1]
            if created < time:
                cs1.execute('update jkb_order as o set o.status=3, o.takeTime=%s where o.id=%s',
                            (datetime.now(), orderId))
                log.info('==========================自动确认收货!')
        # ------
        cs1.execute('select o.orderNo, o.appid, o.created, o.id, o.coupFee from jkb_order as o where o.status = 0')

        result = cs1.fetchall()
        for item in result:
            orderNo = item[0]
            appid = item[1]
            created = item[2]
            orderId = item[3]
            coupFee = item[4]
            cs1.execute('select shop.timeout from jkb_shop as shop where shop.appid=%s', appid)
            # 每个订单的支付超时时间(分)
            timeout = cs1.fetchone()[0]
            start = datetime.now() + timedelta(minutes=-timeout)
            if created < start:
                # print('订单超时了')
                # 如果此订单使用了优惠券还原优惠券之前状态
                if coupFee:
                    cs1.execute('select c.id from jkb_coupon as c where c.appid=%s and c.orderId=%s', (appid, orderId))
                    conponId = cs1.fetchone()[0]
                    cs1.execute('update jkb_coupon as c set c.status=0, c.useTime=null, c.orderId=null where c.id=%s',
                                conponId)
                    log.info('===========================还原优惠券状态!')
                # 更新订单状态
                cs1.execute('update jkb_order set status=4,isClose=1 where orderNo=%s', orderNo)
                # 加库存 减销量
                cs1.execute('select orSku.skuId, orSku.amount from jkb_order_sku as orSku where orderId=%s',
                            orderId)
                orderSkus = cs1.fetchall()

                for ite in orderSkus:  # 取出每个订单sku的  skuid 和 数量
                    skuId = ite[0]
                    amount = ite[1]
                    cs1.execute('select jkb_sku.stock, jkb_sku.spuId from jkb_sku where id=%s', skuId)
                    sku = cs1.fetchone()
                    old_stock = sku[0]
                    spuId = sku[1]
                    new_stock = old_stock + amount
                    # print(old_stock, '---------old_stock')
                    # print(new_stock, '---------new_stock')
                    # 加库存
                    cs1.execute('update jkb_sku set jkb_sku.stock=%s where jkb_sku.id=%s', (new_stock, skuId))
                    # 减销量
                    # 查询销量
                    cs1.execute('select jkb_spu.sales from jkb_spu where jkb_spu.id=%s', spuId)
                    old_sales = cs1.fetchone()[0]
                    new_sales = old_sales - amount
                    cs1.execute('update jkb_spu set jkb_spu.sales=%s where jkb_spu.id=%s', (new_sales, spuId))
                    log.info('============================加库存, 减销量完成!')
        cs1.close()
    except Exception as e:
        log.error('超时订单处理异常:' + str(e))
        conn.rollback()  # 事务回滚
    finally:
        conn.commit()
        conn.close()
    log.info('执行定时任务=================================================')


sched = Scheduler()


@sched.interval_schedule(seconds=3)
def my_task():
    new_task()


# 上线需打开定时任务
# sched.start()


class OrderData(View):
    """
    订单列表&订单详情&创建订单
    """
    def get(self, request):
        user = request.user
        orderId = request.GET.get('orderId')
        shop = Shop.objects.filter(appid=user.appid).first()
        if not shop:
            return gen_resp(20004, 'shop数据不存在')
        timeout = shop.timeout * 60
        # 订单列表
        if not orderId:
            status = request.GET.get('status')
            page = request.GET.get('page', '1')

            if not status:
                return gen_resp(20000, '缺少status参数')

            if status not in ['-1', '0', '1', '2', '3']:
                return gen_resp(20001, 'status格式不正确或超出范围')

            if not str(page).isdigit() or page == '0':
                page = 1
            else:
                page = int(page)

            # 如果状态是-1返回全部订单
            if status == '-1':
                orders = Order.objects.filter(userId=user.id).order_by('-created')
            else:
                orders = Order.objects.filter(userId=user.id, status=status).order_by('-created')

            count = orders.count()
            orderList = []
            for item in orders[(page - 1) * ORDER_PAGE_NUM:page * ORDER_PAGE_NUM]:
                dic = model_2_dict(item, fields=['id', 'orderNo', 'realFee', 'shipFee','isComment'])
                # 订单付款剩余时间
                if item.status == 0:
                    countdown = item.created.timestamp() + timeout - int(time.time())
                    if countdown <= 0:
                        dic['countdown'] = 0
                    else:
                        dic['countdown'] = countdown
                dic['status'] = item.status
                # 订单商品
                order_sku = OrderSku.objects.filter(orderId=item.id)
                dic['orderCount'] = order_sku.count()

                # 下面返回每个sku的信息
                skuList = []
                for item in order_sku:
                    dic2 = {}
                    dic2['amount'] = item.amount
                    sku = Sku.objects.filter(id=item.skuId).first()
                    if sku:
                        dic2['price'] = sku.price
                        dic2['cover'] = sku.cover.url
                        dic2['skuId'] = sku.id
                        spu = Spu.objects.filter(id=sku.spuId).first()
                        if spu:
                            dic2['title'] = spu.title
                            dic2['spuId'] = spu.id

                        # 返回规格
                        # specList = []
                        # spec = Spec.objects.filter(skuId=sku.id)
                        # for item in spec:
                        #     specList.append(model_2_dict(item, exclude=('skuId', 'appid', 'pid')))
                        specList = []
                        attrValue = AttrValue.objects.filter(skuId=sku.id)
                        for item in attrValue:
                            specList.append(model_2_dict(item, fields=('value')))

                        dic2['specList'] = specList
                    skuList.append(dic2)

                dic['skuList'] = skuList
                orderList.append(dic)
            return gen_resp(0, '成功!', **{'orderList': orderList, 'more': page < count / ORDER_PAGE_NUM})
        else:
            order = Order.objects.filter(userId=user.id, id=orderId).first()
            if not order:
                return gen_resp(20004, '订单不存在')

            # 订单信息
            orderData = model_2_dict(order,
                                     fields=['id', 'name', 'phone', 'address', 'isRefund', 'isComment', 'realFee',
                                              'shipFee', 'orderNo', 'created', 'payTime', 'sendTime', 'takeTime',
                                             'payType', 'totalFee', 'coupFee'])
            # 订单付款剩余时间
            if order.status == 0:
                countdown = order.created.timestamp() + timeout - int(time.time())
                if countdown <= 0:
                    orderData['countdown'] = 0
                else:
                    orderData['countdown'] = countdown
            orderData['status'] = order.status
            # Sku信息
            orderSkus = OrderSku.objects.filter(orderId=order.id)
            skuList = []
            for item in orderSkus:
                dic = model_2_dict(item, fields=['amount', 'price'])

                sku = Sku.objects.filter(id=item.skuId).annotate(
                    title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1])).first()
                if sku:
                    dic['cover'] = sku.cover.url if sku.cover else ''
                    dic['skuId'] = sku.id
                    # sku是否有退款
                    refundNo = str(order.orderNo) + '1'
                    orderSkuRefund = OrderSkuRefund.objects.filter(orderSkuId=sku.id, refundNo=refundNo).first()
                    if orderSkuRefund:
                        dic['refundType'] = orderSkuRefund.refundType
                        dic['status'] = orderSkuRefund.status
                    dic['title'] = sku.title
                    dic['spuId'] = sku.spuId
                    # 此商品的规格
                    specList = []
                    attrValue = AttrValue.objects.filter(skuId=sku.id)
                    for item in attrValue:
                        specList.append(model_2_dict(item, fields=('value')))
                    dic['specList'] = specList
                    skuList.append(dic)

            orderData['skuList'] = skuList

            return gen_resp(0, '成功!', **{'order': orderData})

    # 创建订单
    def post(self, request):
        appid = request.APPID
        user = request.user
        data, rsp = check_data_must(request, must=['addrId', 'skuList'])
        if rsp:
            return rsp

        skuList = data.get('skuList')
        if not isinstance(skuList, list) or len(skuList) == 0:
            return gen_resp(20001, 'skuList参数不符合格式或为空')

        addrId = data.get('addrId')
        addr = Addr.objects.filter(userId=user.id, id=addrId).first()
        if not addr:
            return gen_resp(20004, '地址不存在')

        # 是否从购物车
        fromcart = data.get('fromcart')
        # 是否使用优惠券
        couponId = data.get('couponId')
        # 是否有备注
        remark = data.get('remark', '')

        # --------------------------------------------------------------------------------
        # 订单信息
        orderNo = gen_order_no(user.id)
        # tradeNo = gen_trade_no(user.id)   # 生成订单的时候不用创建交易号

        # 收件人名字
        name = addr.name
        # 收件人手机号
        phone = addr.phone
        # 收货地址
        prov = District.objects.filter(id=addr.provId).first()
        provName = prov.name if prov else ''
        city = District.objects.filter(id=addr.cityId).first()
        cityName = city.name if city else ''
        area = District.objects.filter(id=addr.areaId).first()
        areaName = area.name if area else ''

        address = provName + cityName + areaName + addr.detail

        if couponId:
            coupon = Coupon.objects.filter(id=couponId, status=0, userId=user.id).first()
            if not coupon:
                return gen_resp(20004, '优惠券不存在')
            else:
                coupFee = coupon.money
                # 修改优惠券状态 需要创建订单以后再创建
        else:
            coupFee = 0

        try:
            with transaction.atomic():
                # 没加快递费之前的总金额
                totalFe = 0
                # 运费
                shipFee = 0
                orderSkuObjs = []
                for item in skuList:
                    skuId = item.get('skuId')
                    amount = item.get('amount')
                    if not isinstance(amount, int) or amount <= 0:
                        return gen_resp(20001, 'amount参数非整数或者不大于0')

                    sku = Sku.objects.filter(id=skuId).first()
                    if not sku:
                        return gen_resp(20004, f'此skuId不存在:{skuId}')

                    if sku.buyMax != 0:
                        if amount > sku.buyMax:
                            return gen_resp(10001, '超出最大购买量')

                    price = sku.price * amount
                    totalFe += price

                    # 用户地址省id
                    provId = addr.provId
                    # 运费规则
                    ship = Ship.objects.filter(id=Spu.objects.filter(id=sku.spuId).first().shipId).first()

                    # 创建字典对象,方便下面创建订单sku
                    dic = {}
                    dic['skuId'] = skuId
                    dic['amount'] = amount
                    dic['weight'] = sku.weight
                    dic['price'] = sku.price
                    if ship:
                        # 指定规则
                        shipProv = ShipProv.objects.filter(shipId=ship.id, provId=provId).first()
                        # 如果按件计费
                        if ship.shipType == 0:
                            # 指定规则不存在按默认规则
                            if not shipProv:
                                iniFee = ship.iniFee
                                fee = iniFee * amount
                                shipFee += fee
                                dic['shipFee'] = fee
                            else:
                                iniFee = shipProv.iniFee
                                fee = iniFee * amount
                                shipFee += fee
                                dic['shipFee'] = fee
                        # 如果是按重量计费
                        elif ship.shipType == 1:
                            # 此sku总重量
                            weight = sku.weight * amount
                            if not shipProv:
                                # 起始价格
                                iniFee = ship.iniFee
                                # 不大于起始重量的时候
                                if not weight > ship.iniWei:
                                    shipFee += iniFee
                                    dic['shipFee'] = iniFee
                                else:
                                    # 超出重量
                                    beWei = weight - ship.iniWei
                                    # 超出重量价格
                                    beFee = beWei * ship.addFee
                                    fee = iniFee + beFee
                                    shipFee += fee
                                    dic['shipFee'] = fee
                            else:
                                iniFee = ship.iniFee
                                if not weight > shipProv.iniWei:
                                    shipFee += iniFee
                                    dic['shipFee'] = iniFee
                                else:
                                    beWei = weight - shipProv.iniWei
                                    beFee = beWei * shipProv.addFee
                                    fee = iniFee + beFee
                                    shipFee += fee
                                    dic['shipFee'] = iniFee
                        else:
                            # 包邮
                            dic['shipFee'] = 0
                            pass
                    orderSkuObjs.append(dic)
                    # 减库存
                    if amount > sku.stock:
                        return gen_resp(10001, f'此sku库存不足{skuId}')
                    sku.stock -= amount
                    sku.save()
                    # 加销量
                    spuId = sku.spuId
                    spu = Spu.objects.filter(id=spuId).first()
                    spu.sales += amount
                    spu.save()


                # 总金额
                totalFee = totalFe + shipFee
                # 实付款金额
                realFee = totalFee - coupFee
                # --------------------------------------------------------------------下面创建订单
                order = Order.objects.create(
                    appid=user.appid,
                    orderNo=orderNo,
                    # tradeNo=tradeNo,
                    userId=user.id,
                    status=0,
                    remark=remark,
                    payType=0,
                    totalFee=totalFee,
                    realFee=realFee,
                    coupFee=coupFee,
                    shipFee=shipFee,
                    name=name,
                    phone=phone,
                    address=address,
                )
                # 改变优惠券状态, 使用的优惠券关联订单号
                if couponId:
                    coup = Coupon.objects.get(id=couponId)
                    coup.status = 1
                    coup.useTime = datetime.now()
                    coup.orderId = order.id
                    coup.save()
                # 创建ordersku
                for item in orderSkuObjs:
                    OrderSku.objects.create(
                        appid=user.appid,
                        orderId=order.id,
                        skuId=item.get('skuId'),
                        amount=item.get('amount'),
                        price=item.get('price'),
                        shipFee=item.get('shipFee', 0),
                        weight=item.get('weight')
                    )
                # 如果是从购物车生成的订单, 删除购物车sku
                if fromcart:
                    for item in skuList:
                        cart = Cart.objects.filter(userId=user.id, skuId=item.get('skuId')).first()
                        if cart:
                            cart.delete()
                # 更新地址最后使用时间
                addr.useTime = datetime.now()
                addr.save()

                # 下单发送信号
                print("------------下单发送signal---------")
                signal_first_order.send(sender=None, appid=appid, userId=user.id)
                print('end---------signal')

        except Exception as e:
            log.error('创建订单出错' + str(e))
            return gen_resp(10000, '创建订单出错')

        return gen_resp(0, '成功', **{'orderNo': order.orderNo})


def district(request):
    """
    选择省市区
    """

    id = request.GET.get('id')
    if not id:
        district = District.objects.filter(pid=0)
    else:
        if not str(id).isdigit():
            return gen_resp(20001, '参数格式不正确')
        district = District.objects.filter(pid=id)

    data = []
    for item in district:
        data.append(model_2_dict(item, exclude=['appid', 'pid']))

    return gen_resp(0, '成功', **{'data': data})


def coupon(request):
    """
    我的优惠
    """
    user = request.user

    coupon = Coupon.objects.filter(userId=user.id).annotate(
        sendType=Subquery(CoupInfo.objects.filter(id=OuterRef('infoId')).values('sendType')[:1]))
    couponList = []
    for it in coupon:
        dic = model_2_dict(it, exclude=('appid', 'orderId', 'userId', 'infoId'))
        dic['sendType'] = it.sendType
        couponList.append(dic)

    return gen_resp(0, '成功', **{'couponList': couponList})


class Address(View):

    def get(self, request):

        user = request.user

        id = request.GET.get('id')

        if not id:
            addr = Addr.objects.filter(userId=user.id)

            addrList = []
            for item in addr:
                dic = model_2_dict(item, fields=['id', 'name', 'phone', 'detail', 'lng', 'lat'])

                dic['isDefault'] = 1 if item.default else 0

                prov = District.objects.filter(id=item.provId).first()
                # dic['provId'] = prov.id
                dic['prov'] = prov.name

                city = District.objects.filter(id=item.cityId).first()
                # dic['cityId'] = city.id
                dic['city'] = city.name

                area = District.objects.filter(id=item.areaId).first()
                # dic['areaId'] = area.id
                dic['area'] = area.name

                addrList.append(dic)

            return gen_resp(0, '成功', **{"addrList": addrList})

        else:

            if not str(id).isdigit():
                return gen_resp(20001, '参数格式不正确')

            addr = Addr.objects.filter(id=id, userId=user.id).first()
            if not addr:
                return gen_resp(20004, '地址不存在')

            dic = model_2_dict(addr, fields=['id', 'name', 'phone', 'detail', 'lng', 'lat'])

            dic['isDefault'] = 1 if addr.default else 0

            prov = District.objects.filter(id=addr.provId).first()
            # dic['provId'] = prov.id
            dic['prov'] = prov.name

            city = District.objects.filter(id=addr.cityId).first()
            # dic['cityId'] = city.id
            dic['city'] = city.name

            area = District.objects.filter(id=addr.areaId).first()
            # dic['areaId'] = area.id
            dic['area'] = area.name

            return gen_resp(0, '成功', **{"data": dic})

    # 添加或修改地址
    def post(self, request):
        user = request.user
        data, rsp = check_data_must(request, must=['name', 'phone', 'prov', 'city', 'area', 'detail'])
        if rsp:
            return rsp
        id = data.get('id')

        name = data.get('name')
        phone = data.get('phone')
        if not re.match("^1[3-9]\d{9}$", phone):
            return gen_resp(20001, '手机号格式不正确')

        prov = data.get('prov')
        prov1 = District.objects.filter(name=prov).first()
        if not prov1:
            return gen_resp(20004, 'prov查询不存在')

        city = data.get('city')
        city1 = District.objects.filter(name=city).first()
        if not city1:
            return gen_resp(20004, 'city查询不存在')

        area = data.get('area')
        area1 = District.objects.filter(name=area).first()
        if not area1:
            return gen_resp(20004, 'area查询不存在')

        detail = data.get('detail')
        default = data.get('isDefault', 0)
        lng = data.get('lng', 0)
        lat = data.get('lat', 0)
        # 添加
        if not id:
            try:
                with transaction.atomic():
                    if default:
                        # 默认地址只能有一个
                        Addr.objects.filter(userId=user.id, default=1).update(default=0)
                    Addr.objects.create(
                        appid=user.appid,
                        userId=user.id,
                        name=name,
                        phone=phone,
                        provId=prov1.id,
                        cityId=city1.id,
                        areaId=area1.id,
                        detail=detail,
                        default=default,
                        lng=lng,
                        lat=lat
                    )
            except Exception as e:
                log.error('创建地址失败:' + str(e))
                return gen_resp(10000, '创建地址失败')
            return gen_resp(0, '添加地址成功')
        # 修改
        else:
            if not str(id).isdigit():
                return gen_resp(20001, '参数格式不正确')

            addr = Addr.objects.filter(id=id).first()
            if not addr:
                return gen_resp(20004, '此地址数据不存在')
            try:
                with transaction.atomic():
                    if default:
                        # 默认地址只能有一个
                        Addr.objects.filter(userId=user.id, default=1).update(default=0)
                    addr.name = name
                    addr.phone = phone
                    addr.provId = prov1.id
                    addr.cityId = city1.id
                    addr.areaId = area1.id
                    addr.detail = detail
                    addr.default = default
                    addr.lng = lng
                    addr.lat = lat
                    addr.save()
            except Exception as e:
                log.error('修改地址失败:' + str(e))
                return gen_resp(10000, '修改地址失败')

            return gen_resp(0, '修改地址成功')

    # 删除地址
    def delete(self, request):
        user = request.user
        data, rsp = check_data_must(request, ['id'])
        if rsp:
            return rsp
        id = data.get('id')
        addr = Addr.objects.filter(id=id, userId=user.id).first()
        if not addr:
            return gen_resp(20004, '地址不存在')
        try:
            addr.delete()
        except Exception as e:
            log.error('删除地址失败:' + str(e))
            return gen_resp(10000, '删除地址失败')

        return gen_resp(0, '删除成功')


def orderCancel(request):
    """
    取消订单
    """
    user = request.user
    data, rsp = check_data_must(request, must=['orderNo'])
    if rsp:
        return rsp
    orderNo = data.get('orderNo')
    order = Order.objects.filter(orderNo=orderNo, userId=user.id).first()
    if not order:
        return gen_resp(20004, '订单不存在')
    if order.status != 0:
        return gen_resp(10001, '不是待付款订单')
    try:
        with transaction.atomic():
            # 改变订单状态
            order.status = 4
            order.isClose = True
            order.save()
            # 如果使用了优惠券, 还原优惠券
            if order.coupFee != 0:
                coupon = Coupon.objects.filter(userId=user.id, orderId=order.id).first()
                if coupon:
                    coupon.status = 0
                    coupon.useTime = None
                    coupon.orderId = None
                    coupon.save()
            # 还原库存
            order_sku = OrderSku.objects.filter(orderId=order.id)
            for item in order_sku:
                skuId = item.skuId
                sku = Sku.objects.filter(id=skuId).first()
                sku.stock += item.amount
                sku.save()
                # 还原销量
                spu = Spu.objects.filter(id=sku.spuId).first()
                spu.sales -= item.amount
                spu.save()
    except Exception as e:
        log.error('取消订单失败:' + str(e))
        return gen_resp(10000, '取消订单失败')
    return gen_resp(0, '取消订单成功')


def orderConfirm(request):
    """
    确认收货
    """
    user = request.user
    orderId = request.GET.get('orderId')
    if not str(orderId).isdigit():
        return gen_resp(20001, '缺少参数或者参数格式不正确')

    order = Order.objects.filter(id=orderId, userId=user.id).first()
    if not order:
        return gen_resp(20004, '数据不存在')

    if order.status != 2:
        return gen_resp(10001, '不是待收货状态')

    try:
        order.status = 3
        order.takeTime = datetime.now()
        order.save()
    except Exception as e:
        log.error('确认收货失败:' + str(e))
        return gen_resp(10000, '确认收货失败')

    return gen_resp(0, '确认收货成功')


# 申请退款
@csrf_exempt
def orderSkuRefund(request):
    user = request.user
    data, rsp = check_data_must(request, must=['orderNo', 'orderSkuId', 'refundType', 'reason', 'refundFee', 'image'])
    if rsp:
        return rsp

    orderNo = data.get('orderNo')
    orderSkuId = data.get('orderSkuId')
    refundType = data.get('refundType')
    reason = data.get('reason')
    refundFee = data.get('refundFee')
    image = data.get('image')
    remark = data.get('remark', '')

    if not str(orderNo).isdigit():
        return gen_resp(20001, 'orderNo参数格式不正确')

    if not isinstance(image, list) or len(image) == 0:
        return gen_resp(20001, 'cmtImg参数不符合格式或为空')

    order = Order.objects.filter(orderNo=orderNo, userId=user.id).first()
    if not order:
        return gen_resp(20004, '订单不存在')

    if not str(orderSkuId).isdigit():
        return gen_resp(20001, 'orderSkuId参数格式不正确')
    orderSku = OrderSku.objects.filter(orderId=order.id, skuId=orderSkuId).first()
    if not orderSku:
        return gen_resp(20004, '订单sku不存在')

    if refundType not in [0, 1, 2]:
        return gen_resp(20001, 'refundType参数错误')

    if reason not in [0, 1, 2]:
        return gen_resp(20001, 'reason参数错误')

    if refundType == 0:
        if order.status != 1:
            return gen_resp(10000, '不是待发货状态')
    if refundType in [1, 2]:
        if order.status != 3:
            return gen_resp(10000, '不是已完成状态')

    if OrderSkuRefund.objects.filter(appid=user.appid, orderSkuId=orderSkuId, refundNo=str(order.orderNo) + '1').exists():
        return gen_resp(10000, '重复提交')

    try:
        with transaction.atomic():
            # 创建 订单售后表 数据
            orderSkuRefund = OrderSkuRefund.objects.create(
                appid=user.appid,
                orderSkuId=orderSkuId,
                refundType=refundType,
                refundNo=str(order.orderNo) + '1',
                refundFee=refundFee,
                reason=reason,
                remark=remark,
            )
            for item in image:
                # 创建 退货凭证表 数据
                RefundImg.objects.create(
                    appid=user.appid,
                    image=item,
                    orderSkuId=orderSkuRefund.id,
                )
    except Exception as e:
        log.error('退款申请提交失败:' + str(e))
        return gen_resp(10000, '退款申请提交失败')

    return gen_resp(0, '已提交')


def orderPay(request):
    """
    支付
    """
    data, rsp = check_data_must(request, must=['orderNo', 'title'])
    if rsp:
        return rsp

    user = request.user
    orderNo = data.get('orderNo')
    order = Order.objects.filter(orderNo=orderNo, userId=user.id).first()

    if not order:
        return gen_resp(20004, '订单不存在')
    if order.status != 0:
        return gen_resp(10001, '订单不是待付款状态')
    if order.isClose:
        return gen_resp(10001, '订单已关闭')

    shop = Shop.objects.filter(appid=user.appid).first()
    if not shop:
        return gen_resp(20005, '商户不存在')

    # 支付倒计时
    timeout = shop.timeout * 60
    if (time.time() - order.created.timestamp()) > timeout:
        return gen_resp(10000, '订单已经超时, 请重新下单')

    #  转化为分
    total_fee = int(order.realFee * 100)

    # 每次生成交易号
    tradeNo = gen_trade_no(user.id)
    order.tradeNo = tradeNo
    order.save()

    tmp = {
        'openid': user.openid,
        'appid': user.appid,
        'mch_id': shop.mchId,
        'nonce_str': ''.join(random.sample(string.ascii_letters + string.digits, 12)),
        'body': data.get('title'),
        'out_trade_no': tradeNo,
        # 'total_fee': total_fee,
        "total_fee": 1,  # 测试付款一分钱 上线删除
        'spbill_create_ip': request.META['REMOTE_ADDR'],
        'notify_url': NOTI_URL,
        'trade_type': "JSAPI",
    }
    tmp['sign'] = wx_sign(tmp, shop.mchKey)
    try:
        # 转成xml
        xml = xmltodict.unparse({"xml": tmp}, full_document=False)

        resp = requests.post('https://api.mch.weixin.qq.com/pay/unifiedorder', data=xml.encode())

        ret = xmltodict.parse(resp.content.decode())["xml"]

        # 统一下接口请求出错
        if ret['return_code'] != 'SUCCESS':
            return gen_resp(10000, ret["return_msg"])

        if ret["result_code"] != "SUCCESS":
            log.error('{} uniorder code|des {}:{}'.format(orderNo, ret["err_code"], ret["err_code_des"]))
            return gen_resp(10000, '微信请求出错')

        # 如果都没错的话
        wxdata = {
            'appId': user.appid,
            'nonceStr': ''.join(random.sample(string.ascii_letters + string.digits, 12)),
            'timeStamp': str(int(time.time())),
            'package': "prepay_id=" + ret["prepay_id"],
            'signType': 'MD5'
        }
        wxdata['paySign'] = wx_sign(wxdata, shop.mchKey)

        return gen_resp(0, '成功', data=wxdata)
    except Exception as e:
        log.error('微信下单失败:{} {}'.format(orderNo, e))
        return gen_resp(10000, '微信下单失败')


class FavorView(View):

    def get(self, request):
        """
        我的收藏
        """
        user = request.user
        objType = request.GET.get('objType')
        page = request.GET.get('page', '1')

        if not str(page).isdigit() or page == '0':
            page = 1
        else:
            page = int(page)

        if not str(objType).isdigit():
            return gen_resp(20001, '缺少参数或者参数格式不正确')

        favor = Favor.objects.filter(userId=user.id, objType=objType)
        count = favor.count()
        favorData = favor[(page - 1) * ORDER_PAGE_NUM:page * ORDER_PAGE_NUM]

        # 收藏的对象是商品
        if int(objType) == 0:
            spuId = list(favorData.values_list('objId', flat=True))

            spus = Spu.objects.filter(id__in=spuId).annotate(
                min_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('price')[:1]),
                max_price=Subquery(Sku.objects.filter(spuId=OuterRef('id')).values('price').order_by('-price')[:1])
            )
            spuList = []
            for item in spus:
                dic = model_2_dict(item, fields=['title', 'subtitle', 'cover', 'state'])
                dic['spuId'] = item.id
                priceMin = item.min_price
                priceMax = item.max_price
                price = str(priceMin) + '-' + str(priceMax) if priceMin != priceMax else str(priceMin)
                dic['price'] = price
                spuList.append(dic)

            return gen_resp(0, '成功', spuList=spuList, more=page < count / ORDER_PAGE_NUM)
        else:
            return gen_resp(20004, '目前没有此类型对象')

    # 收藏、取消收藏
    def post(self, request):
        user: User = request.user
        data, rsp = check_data_must(request, ['spuId', 'objType', 'isFavor'])
        if rsp:
            return rsp
        isFavor = data.get('isFavor')
        if isFavor not in [1, 0]:
            return gen_resp(20001, msg="isFavor参数或参数类型错误")
        spuId = data.get('spuId')
        if not str(spuId).isdigit():
            return gen_resp(20001, msg="spuId参数类型错误")
        objType = data.get('objType')
        if not str(objType).isdigit():
            return gen_resp(20001, msg="objType参数类型错误")

        if not Spu.objects.filter(id=int(spuId)).exists():
            return gen_resp(20000, msg="spuId为{}的商品不存在".format(spuId))
        favor = Favor.objects.filter(userId=user.id, objId=int(spuId), objType=int(objType)).first()
        if int(isFavor) == 1:
            if not favor:
                Favor.objects.create(userId=user.id, objId=int(spuId), appid=user.appid)
            return gen_resp(0, isFavor=1, msg="收藏成功")
        else:
            if favor:
                favor.delete()
            return gen_resp(0, isFavor=0, msg="取消收藏成功")


def orderStatus(request):
    """
    查看订单状态
    """
    appid = request.APPID
    user = request.user
    orderNo = request.GET.get('orderNo')

    if not orderNo:
        return gen_resp(20000, 'orderNo参数不存在')
    if not str(orderNo).isdigit():
        return gen_resp(20001, 'orderNo参数格式不正确')

    order = Order.objects.filter(orderNo=orderNo, userId=user.id).first()
    if not order:
        return gen_resp(20004, '订单数据不存在')

    shop = Shop.objects.filter(appid=order.appid).first()
    if not shop:
        return gen_resp(20004, '商户不存在')

    # 如果订单是未付款状态
    if order.status == 0:
        data = {
            "appid": shop.appid,
            "mch_id": shop.mchId,
            "out_trade_no": order.tradeNo,
            "nonce_str": ''.join(random.sample(string.ascii_letters + string.digits, 12))
        }
        data["sign"] = wx_sign(data, shop.mchKey)

        try:
            xml = xmltodict.unparse({"xml": data}, full_document=False)
            rsp = requests.post('https://api.mch.weixin.qq.com/pay/orderquery', data=xml.encode())
            ret = xmltodict.parse(rsp.content.decode())["xml"]
            log.debug('check trade: {}'.format(order.orderNo))

            if ret.get('return_code') != "SUCCESS":
                log.error('check trade fail0:{} {}'.format(order.orderNo, ret.get('return_msg')))
            elif ret.get('trade_state') != "SUCCESS":
                log.error('check trade fail1:{} {}'.format(order.orderNo, ret.get('trade_state_desc ')))
            else:
                try:
                    # 查询支付成功,改变订单状态
                    time_end = ret.get('time_end')
                    payTime = datetime.strptime(time_end, '%Y%m%d%H%M%S')
                    order.payTime = payTime
                    order.status = 1
                    order.payNoti = 3
                    order.save()
                    log.info('check trade ok: {}'.format(order.orderNo))
                    # 支付成功
                    print("------------signal---------")
                    signal_pay.send(sender=None, appid=appid, oid=order.id)
                    print('end---------signal')
                except Exception as e:
                    log.error('修改订单状态失败:' + str(e))
                    return gen_resp(10000, '修改订单状态失败')

        except Exception as e:
            log.error('查询微信失败: {} {}'.format(order.orderNo, e))

    return gen_resp(0, '成功', status=order.status)


def payNoti(request):
    """
    支付回调
    """
    log.info('微信支付回调数据: {}'.format(request.body.decode()))

    try:
        data = xmltodict.parse(request.body.decode()).get("xml", {})
    except Exception as e:
        log.error('支付回调数据处理异常:{}'.format(e))
        return wx_reply("数据处理异常")

    if "sign" not in data:
        log.error('支付回调数据没有sign字段:{}'.format(data))
        return wx_reply("没有sign字段")

    if data["return_code"] != "SUCCESS":
        log.error('支付回调通信错误:{}'.format(data["return_msg"]))
        return wx_reply("通信错误")

    appid = data.get('appid')
    shop = Shop.objects.filter(appid=appid).first()
    if not shop:
        return wx_reply("数据错误")
    mchKey = shop.mchKey

    sign = data.pop("sign")
    if sign != wx_sign(data, mchKey):
        log.error('支付回调签名错误')
        return wx_reply("签名错误")

    tradeNo = data["out_trade_no"]

    order = Order.objects.filter(tradeNo=tradeNo).first()
    if order is None:
        err_msg = "订单不存在:{}".format(tradeNo)
        log.error('支付回调取的交易号不存在:{}'.format(err_msg))
        return wx_reply(err_msg)

    if order.payNoti in [1, 3]:
        return wx_reply()

    if data["result_code"] != "SUCCESS":
        log.error('交易号为:{}的订单未支付成功|错误码和描述 {}:{}'.format(order.tradeNo, data["err_code"], data["err_code_des"]))
        order.tradeNo = 2
        order.save()
        return wx_reply()

    if order.status != 0:
        log.error("此交易号:{}的订单状态不是待付款｜它的状态是：{}".format(order.tradeNo, order.status))
        return wx_reply()

    try:
        # 通知支付成功以后改变订单状态
        time_end = data['time_end']
        payTime = datetime.strptime(time_end, '%Y%m%d%H%M%S')

        order.status = 1
        order.payNoti = 1
        # order.payTime = datetime.now()
        order.payTime = payTime
        order.save()
        # 支付成功
        print("------------signal---------")
        signal_pay.send(sender=None, appid=appid, oid=order.id)
        print('end---------signal')
    except Exception as e:
        log.error('订单号:{}状态更新失败:{}'.format(order.orderNo, e))
        return wx_reply(msg='更新订单状态失败')
    return wx_reply()


def qiniuToken(request):
    """
    获取七牛云token
    """
    try:
        q = qiniu.Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
        token = q.upload_token(QINIU_BUCKET_NAME, None, 3600)
    except Exception as e:
        log.error('获取七牛云token失败:' + str(e))
        return gen_resp(10000, '获取七牛云token失败')

    return gen_resp(0, '获取成功', token=token)


def shipFee(request):
    """
    快递费
    """
    user = request.user
    data, rsp = check_data_must(request, must=['skuList', 'id'])
    if rsp:
        return rsp

    skuList = data.get('skuList')
    id = data.get('id')

    if not str(id).isdigit():
        return gen_resp(20001, msg="id参数类型错误")

    addr = Addr.objects.filter(userId=user.id, id=id).first()
    if not addr:
        return gen_resp(20004, '地址不存在')

    skuList = eval(skuList)

    if not isinstance(skuList, list) or len(skuList) == 0:
        return gen_resp(20001, 'skuList参数不符合格式或为空')

    provId = addr.provId

    try:
        Fee = 0
        for item in skuList:
            skuId = item.get('skuId')
            if not skuId:
                return gen_resp(20000, 'skuId参数不存在')
            sku = Sku.objects.filter(id=skuId).first()
            if not sku:
                return gen_resp(20004, 'sku数据查询不存在')

            amount = item.get('amount')
            if not amount:
                return gen_resp(20000, 'amount参数不存在')

            if not isinstance(amount, int) or amount <= 0:
                return gen_resp(20001, 'amount参数非整数或者不大于0')
            spuId = sku.spuId
            spu = Spu.objects.filter(id=spuId).first()
            if not spu:
                return gen_resp(20004, 'spu数据查询不存在')

            ship = Ship.objects.filter(id=spu.shipId).first()
            if not ship:
                return gen_resp(20004, 'ship数据查询不存在')

            # 查询是否指定省份
            shipProv = ShipProv.objects.filter(shipId=ship.id, provId=provId).first()

            if ship.shipType == 0:
                if not shipProv:
                    fee = ship.iniFee * amount
                    Fee += fee
                else:
                    fee = shipProv.iniFee * amount
                    Fee += fee

            if ship.shipType == 1:
                if not shipProv:
                    # 起始费用
                    iniFee = ship.iniFee
                    # 起始重量
                    iniWei = ship.iniWei
                    if not sku.weight * amount > iniWei:
                        Fee += iniFee
                    else:
                        # 超出重量
                        beWei = sku.weight * amount - iniWei
                        # 超出费用
                        beFee = beWei * ship.addFee
                        fee = iniFee + beFee
                        Fee += fee
                else:
                    # 起始费用
                    iniFee = shipProv.iniFee
                    # 起始重量
                    iniWei = shipProv.iniWei
                    if not sku.weight * amount > iniWei:
                        Fee += iniFee
                    else:
                        # 超出重量
                        beWei = sku.weight * amount - iniWei
                        # 超出费用
                        beFee = beWei * shipProv.addFee
                        fee = iniFee + beFee
                        Fee += fee
            else:
                pass
    except Exception as e:
        log.error('计算运费出错:' + str(e))
        return gen_resp(10000, '计算运费出错')

    return gen_resp(0, '成功', Fee=Fee)


def tagCmt(request):
    """
    展示评论标签
    """
    user = request.user
    tagCmts = TagCmt.objects.filter(appid=user.appid)

    tagCmtList = []
    for item in tagCmts:
        tagCmtList.append(model_2_dict(item, exclude=['appid']))

    return gen_resp(0, '成功', tagCmtList=tagCmtList)
