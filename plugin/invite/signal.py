from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.dispatch import receiver
from plugin.invite.models import *
from lib import gen_resp
from lib.signals import *
from main.models import Order, ShareRecord, ShareMark, Shop, OrderSku, OrderSkuRefund


# @receiver(signal_first_visit)
# def my_callback(sender, **kwargs):
#     print("cccalll", "-------------")
#     print(sender, kwargs.get('aa'))


def createPids(appid, userId, shareBy, becom):
    """
    创建用户层级记录 # 判断称为分销商是否需要申请
    :return:
    """
    pid = UidPid.objects.filter(uid=shareBy).first()
    # 判断该用户是否有资格分享
    status = 0 if becom == 0 else 1
    if not pid:
        try:
            UidPid.objects.create(appid=appid, uid=userId, pid1=shareBy, status=status, created=datetime.now())
            return gen_resp(0, msg="userId为{}的用户层级关系创建成功".format(userId))
        except Exception as err:
            log.error("用户层级关系创建失败{}".format(err))
            return gen_resp(10000, msg="用户层级关系创建失败")
    else:
        try:
            UidPid.objects.create(
                appid=appid,
                uid=userId,
                pid1=shareBy,
                pid2=pid.pid1,
                pid3=pid.pid2,
                status=status,
                created=datetime.now()
            )
            return gen_resp(0, msg="userId为{}的用户层级关系创建成功".format(userId))
        except Exception as err:
            log.error("用户层级关系创建失败{}".format(err))
            return gen_resp(10000, msg="用户层级关系创建失败")


@receiver(signal_first_visit)
def share(sender, **kwargs):
    """
    创建分享记录
    appid, markId, shareBy, userId
    :return:
    """
    # 判断佣金系统是否开启

    appid = kwargs.get('appid')
    userId = kwargs.get('userId')
    shareBy = kwargs.get('shareBy')
    markId = kwargs.get('markId')
    if not (shareBy or markId):
        return gen_resp(0, msg="该用户不是分享注册")
    shop = Shop.objects.filter(appid=appid).first()
    log.info('创建分享记录参数{}shop.useRate{}'.format(kwargs, shop.useRate))
    conf = Conf.objects.filter(appid=appid).first()
    if not conf:
        return gen_resp(20001, msg="appid为{}的分销配置记录不存在".format(conf))

    if shop.useRate and conf.enable != 0:
        # 先判断是否有用户层级  判断是否有分享记录
        if UidPid.objects.filter(uid=userId, status=0).exists():
            return gen_resp(20004, msg="userId为{}的用户层级已存在".format(userId))
        # 判断称为分销商是否需要申请 shareBy是否有分销资格
        sbUP = UidPid.objects.filter(uid=shareBy).first()
        if not sbUP:
            return gen_resp(20003, msg="shareBy为空或者shareBy为{}的记录不存在".format(shareBy))
        if conf.become == 0 and sbUP.status == 0:
            return gen_resp(0, msg="该用户没有分销资格")
        hasRcd = ShareRecord.objects.filter(userId=userId).first()
        if not hasRcd or conf.rule == 1:  # 还没有分享记录 或规则是首次下单
            if not markId or not ShareMark.objects.filter(id=markId).exists():
                return gen_resp(20004, msg="markId为空或者markId为{}的记录不存在".format(markId))
            try:
                ShareRecord.objects.create(
                    markId=markId,
                    userId=userId,
                    shareBy=shareBy,
                    appid=appid
                )
            except Exception as err:
                log.error("创建分享记录失败{}".format(err))
                return gen_resp(10000, msg="分享记录创建失败")
        # 判断是否是首次进入绑定
        if conf.rule == 0:
            # 先判断是否绑定过！！！上边已做判断（信号在多个接口都会发送，所以要注意避免重复创建数据库记录）
            print("首次进入---createPids")
            createPids(appid, userId, shareBy, conf.become)
        return gen_resp(0, msg="分享记录创建成功")
    else:
        return gen_resp(0, msg="该商户未启用佣金系统")


@receiver(signal_first_order)
def orderPids(sender, **kwargs):
    """
    下单绑定用户层级
    :return:
    """
    appid = kwargs.get('appid')
    userId = kwargs.get('userId')
    shop = Shop.objects.filter(appid=appid).first()
    conf = Conf.objects.filter(appid=appid).first()
    log.info("下单创建用户层级参数{}useRate{}".format(kwargs, shop.useRate))
    if not conf:
        return gen_resp(20001, msg="appid为{}的分销配置记录不存在".format(conf))

    if shop.useRate and conf.enable != 0 and conf.rule == 1:

        if UidPid.objects.filter(uid=userId, status=0).exists():
            return gen_resp(20003, msg="userId为{}的用户层级已存在".format(userId))

        shrcod = ShareRecord.objects.filter(appid=appid, userId=userId).order_by('-created').first()
        if not shrcod:
            return gen_resp(20001, msg="userId为{}的用户分享记录不存在".format(userId))
        shareBy = shrcod.shareBy
        sbUP = UidPid.objects.filter(uid=shareBy).first()
        if not sbUP:
            return gen_resp(20003, msg="shareBy为空或者shareBy为{}的记录不存在".format(shareBy))
        # 要注意！！！这里创建用户层级之前是否需要判断
        # 判断shareBy是否有资格分享
        if conf.become == 0 and sbUP.status == 0:
            return gen_resp(0, msg="该用户没有分销资格")
        createPids(appid, userId, shareBy, conf.become)
        return gen_resp(0, msg="下单创建用户层级成功")
    else:
        return gen_resp(0, msg="该商户未启用佣金系统")


@receiver(signal_pay)
def pay(sender, **kwargs):
    """
    支付成功创建消费记录，记录提现
    :return:
    """
    appid = kwargs.get('appid')
    oid = kwargs.get('oid')
    shop = Shop.objects.filter(appid=appid).first()
    conf = Conf.objects.filter(appid=appid).first()
    log.info("下单创建用户层级参数{}useRate{}".format(kwargs, shop.useRate))

    if not conf:
        return gen_resp(20001, msg="appid为{}的分销配置记录不存在".format(conf))

    if shop.useRate and conf.enable != 0:
        order = Order.objects.filter(id=oid).first()
        if not order:
            return gen_resp(20001, msg="oid为{}的订单不存在".format(oid))
        pids = UidPid.objects.filter(uid=order.userId, status=0).first()
        if not pids:
            return gen_resp(20001, msg="userId为{}的用户层级记录不存在".format(order.userId))

        rate = str(conf.rate1) + ',' + str(conf.rate2) + ',' + str(conf.rate3)
        try:
            with transaction.atomic():
                # 创建消费记录
                uidf = UidFee()
                uidf.appid = order.appid
                uidf.oid = oid
                uidf.uid = order.userId
                uidf.money = order.realFee
                uidf.fee1 = order.realFee * conf.rate1
                uidf.fee2 = order.realFee * conf.rate2 if pids.pid2 else 0
                uidf.fee3 = order.realFee * conf.fee3 if pids.pid3 else 0
                uidf.rate = rate
                # 备注
                uidf.remark = 0
                uidf.save()
                # 创建记录提现
                CashOut.objects.create(appid=order.appid, rid=uidf.id, idx=1, pid=pids.pid1, status=0)
                if pids.pid2:
                    CashOut.objects.create(appid=order.appid, rid=uidf.id, idx=2, pid=pids.pid2, status=0)
                if pids.pid3:
                    CashOut.objects.create(appid=order.appid, rid=uidf.id, idx=3, pid=pids.pid3, status=0)
                return gen_resp(0, msg="消费记录,记录提现创建成功")
        except Exception as err:
            log.error("消费记录创建失败{}".format(err))
            return gen_resp(10000, msg="消费记录创建失败")
    else:
        return gen_resp(0, msg="该商户未启用佣金系统")


@receiver(signal_refund)
def refund(sender, **kwargs):
    """
    消费记录 、记录提现
    :return:
    """
    appid = kwargs.get('appid')
    oid = kwargs.get('oid')
    shop = Shop.objects.filter(appid=appid).first()
    conf = Conf.objects.filter(appid=appid).first()
    if not conf:
        return gen_resp(20001, msg="appid为{}的分销配置记录不存在".format(conf))
    print(kwargs, shop.useRate)
    if shop.useRate and conf.enable != 0:
        order = Order.objects.filter(id=oid).first()
        if not order:
            return gen_resp(20001, msg="oid为{}的订单找不到".format(oid))
        if order.isRefund:
            oSkuIdList = list(OrderSku.objects.filter(orderId=oid).values_list('id', flat=True))
            oSkuRe = OrderSkuRefund.objects.filter(orderSkuId__in=oSkuIdList)
            if len(oSkuRe) == len(oSkuIdList):
                # 全部退款
                try:
                    with transaction.atomic():
                        uidFee = UidFee.objects.filter(oid=oid).first()
                        if uidFee:
                            uidFee.delete()
                        cashOut = CashOut.objects.filter(rid=uidFee.id).first()
                        if cashOut:
                            cashOut.delete()
                        return gen_resp(0, msg="消费记录、记录提现删除成功")
                except Exception as err:
                    log.error("消费记录、记录提现删除失败{}".format(err))
                    return gen_resp(10000, msg="消费记录、记录提现删除失败")
            else:
                # 部分退款
                oSkuRe = oSkuRe.aggregate(reFee=Sum('refundFee'))
                reFee = oSkuRe.get('reFee')
                uidFee = UidFee.objects.filter(oid=oid).first()
                if uidFee:
                    # 更新佣金
                    uidFee.money = uidFee.money - reFee
                    rateList = uidFee.rate.split(',')
                    uidFee.fee1 = uidFee.money * Decimal(rateList[0])
                    uidFee.fee2 = uidFee.money * Decimal(rateList[1]) if uidFee.fee2 else uidFee.fee2
                    uidFee.fee3 = uidFee.money * Decimal(rateList[2]) if uidFee.fee3 else uidFee.fee3
                    uidFee.remark = '部分退款'
                    try:
                        uidFee.save()
                        return gen_resp(0, msg="消费记录佣金更新成功")
                    except Exception as err:
                        log.error("消费记录佣金更新失败{}".format(err))
                        return gen_resp(10000, msg="消费记录佣金更新失败")

        else:
            return gen_resp(0, msg="该订单未发生退款")
    else:
        return gen_resp(0, msg="该商户未启用佣金系统")

# def orderPids(appid, userId):
#     """
#     创建用户层级记录 rule(0, '首次点击连接'), (1, '首次下单')
#     :return:
#     """
#     # 首次下单绑定 shareBy
#     record = ShareRecord.objects.filter(appid=appid, userId=userId).order_by('created').first()
#     if not record:
#         return gen_resp(20001, msg="userId为{}的用户没有邀请人".format(userId))
#     shareBy = record.shareBy
#     pid = UidPid.objects.filter(appid=appid, userId=shareBy).first()
#     if not pid:
#         try:
#             UidPid.objects.create(appid=appid, userId=userId, pid1=shareBy)
#         except Exception as err:
#             log.error("用户层级关系创建失败{}".format(err))
#             return gen_resp(10000, msg="用户层级关系创建失败")
#     try:
#         UidPid.objects.create(
#             appid=appid,
#             userId=userId,
#             pid1=shareBy,
#             pid2=pid.pid1,
#             pid3=pid.pid2
#         )
#         return gen_resp(0, msg="userId为{}的用户层级关系创建成功".format(userId))
#     except Exception as err:
#         log.error("用户层级关系创建失败{}".format(err))
#         return gen_resp(10000, msg="用户层级关系创建失败")
