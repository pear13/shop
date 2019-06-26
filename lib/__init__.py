import json
import logging
import random
import string
import time
import hashlib
import xmltodict

from itertools import chain
from enum import Enum, unique
from datetime import datetime

from django.db.models import DateTimeField, ImageField, FileField
from django.http import HttpResponse
from django.http import JsonResponse, request
from django.utils.html import format_html

log = logging.getLogger()


@unique
class Code(Enum):
    """
    错误码定义 <错误级别1位|服务模块2位|具体错误2位>20501  参考微博 https://open.weibo.com/wiki/Error_code
    级别：1系统级错误, 具体处理外的错误，主要在中间件/顶级装饰器中
         2服务级错误, 具体接口中出现的错误
    模块：00本地处理异常
         01微信接口异常
         02短信接口异常
    """
    SUCCESS = (0, '成功')
    UNKNOWN = (10000, '未知错误')
    ILLEGAL = (10001, '非法请求')
    SYSTEM_BUSY = (10002, '系统繁忙')
    SIGN_ERROR = (10003, '签名错误')
    TOKEN_EXPIRED = (10004, 'token过期')
    PARAM_MISS = (20000, '缺少参数')
    PARAM_ERROR = (20001, '参数错误')
    NAME_PASSWORD_ERROR = (20002, '用户名或密码错误')
    DATA_EXISTED = (20003, '数据已存在')
    DATA_NOT_FOUND = (20004, '数据不存在')
    USER_NOT_FOUND = (20005, '用户不存在')
    INVALID_CODE = (20201, '验证码错误')


class RespData(Exception):
    """
    使用抛异常的方式直接返回结果，不需要
    """

    def __init__(self, data: dict):
        super(RespData, self).__init__()
        self.data = data

    def __str__(self):
        return ''


def model_2_dict(instance, fields=None, exclude=None):
    """
    自定义model转字典，处理文件时自动加域名，处理时间时转换
    :param instance:
    :param host: model中有图片/文件字段时，设置此项添加域名
    :param fields:
    :param exclude:
    :return:
    """
    opts = instance._meta
    data = {}
    for f in chain(opts.concrete_fields, opts.private_fields, opts.many_to_many):
        # if not getattr(f, 'editable', False):
        #     print('edit:', f.name)
        #     continue
        if f.name == 'deleted':
            continue
        if fields and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue

        if isinstance(f, (ImageField, FileField)):
            tmp = f.value_from_object(instance)
            data[f.name] = tmp.url if tmp else ''
        elif isinstance(f, DateTimeField):
            tmp = f.value_from_object(instance)
            data[f.name] = int(tmp.timestamp()) if tmp else None
        else:
            data[f.name] = f.value_from_object(instance)
    return data


def gen_resp(code: [int, Code] = 0, msg: str = '', **kwargs):
    """
    对返回内容进行编码处理
    返回数据以key=val的形式提供


    :param code: int 或 错误枚举类型
    :param msg:
    :param kwargs: 实际需要返回的数据
    :return: JsonResponse
    """
    if isinstance(code, Code):
        kwargs = {'code': code.value[0], 'msg': code.value[1] + msg}
    else:
        kwargs.update({'code': code, 'msg': msg})
    return JsonResponse(kwargs, json_dumps_params={'ensure_ascii': False})


def get_save_path(model, fname: str):
    """
    文件名保存规则
    最好是能将商户ID放到路径，这样每个商户的图片不会太多，就不需要加太多的路径
    :param model:
    :param fname:
    :return:
    """
    ext = fname[fname.rindex('.'):]
    now = datetime.now()
    key = hashlib.md5((model.appid + str(now) + fname).encode()).hexdigest()[-20:]

    from main.models import Merc  # 避免循环import
    merc = Merc.objects.filter(appid=model.appid).first()

    new_fname = f"{now.strftime('%Y/%m/%d')}/{key+ext}"
    if merc:
        new_fname = f'{merc.id}/{new_fname}'
    return new_fname


def show_img(obj, w=50, h=50):
    """
    url 转图片显示, 仅用于admin
    :param obj:
    :param w:
    :param h:
    :return:
    """

    return format_html('<a href="{0}"><img style="width:{1}px;height:{2}px" src="{0}" /></a>',
                       obj.url if obj else '', w, h)


def show_video(obj, w=80, h=80):
    """

    :param obj:
    :param w:
    :param h:
    :return:
    """
    return format_html('<a href="{0}"><img style="width:{1}px;height:{2}px" src="{0}" /></a>',
                       obj.url if obj else '', w, h)


def check_data_must(req, must=[]):
    """
    检测必须参数
    :param req:
    :param must: 必须参数
    :return:
    """
    try:
        if not isinstance(req, request.HttpRequest):
            raise Exception('req 不是django.http.request对象')

        if req.method == "GET":
            data = req.GET
        else:
            data = json.loads(req.body.decode('utf8'))

        log.info('{} {} {}'.format(req.method, req.path, data))

        for key in must:
            if key not in data or data[key] == '':
                return data, gen_resp(20000, key+'参数为空')

        return data, None

    except Exception as err:
        log.error('请求数据异常: err:{}'.format(err))
        return None, gen_resp(20001, '请求数据异常或类型错误')

def gen_order_no(userid, cli=1, pay=0, bus=0):
    """
    订单生成规则， {客户渠道}{支付渠道}{业务编号}{年月日}{随机}{用户ID}
    1001031
    客户渠道：1小程序, 2客户端
    支付渠道：0微信, 1支付宝, 2银行卡
    业务编号：0炭
    时间月日：取年月日，方便快速定位时间
    用户编号：4位固定, 用户量
    随机号码：防重复2位，(单个用户一天订单量不会太多)，扩展时优先扩展此字段

    :param userid: 用户ID
    :param cli: 客户渠道
    :param pay: 支付渠道
    :param bus: 业务类型
    :return:
    """

    return '{}{}{}{}{}{}'.format(
        cli,
        pay,
        bus,
        time.strftime('%Y%m%d')[2:],
        '{:0>4}'.format(userid)[-4:],
        ''.join(random.sample(string.digits, 3))
    )

def gen_trade_no(userid):
    """
    订单生成规则， {客户渠道}{支付渠道}{业务编号}{年月日}{随机}{用户ID}
    1001031
    客户渠道：1小程序, 2客户端
    支付渠道：0微信, 1支付宝, 2银行卡
    业务编号：0炭
    时间月日：取年月日，方便快速定位时间
    用户编号：4位固定, 用户量
    随机号码：防重复2位，(单个用户一天订单量不会太多)，扩展时优先扩展此字段

    :param userid: 用户ID
    :param cli: 客户渠道
    :param pay: 支付渠道
    :param bus: 业务类型
    :return:
    """

    return '{}{}{}'.format(
        time.strftime('%Y%m%d')[2:],
        '{:0>4}'.format(userid)[-4:],
        ''.join(random.sample(string.digits, 6))
    )

def wx_sign(data, secret):
    """
    微信签名
    :param data:
    :param secret: 签名秘钥
    :return:
    """

    src = ''
    for key in sorted(data):
        if data[key]:
            src += '{}={}&'.format(key, data[key])
    src += "key="+secret
    sign = hashlib.md5(src.encode('utf-8')).hexdigest().upper()
    return sign

def wx_reply(msg=None):
    return HttpResponse(xmltodict.unparse({
        "xml": {
            "return_code": "FAIL" if msg else "SUCCESS",
            "return_msg": msg
        }
    }, full_document=False))