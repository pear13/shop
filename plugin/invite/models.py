from django.db import models

from main.models import Base


class Conf(Base):
    """
    分销配置表
    """

    enable = models.SmallIntegerField('分销层级', choices=(
        (0, '不开启'), (1, '一级分销'), (2, '二级分销'), (3, '三级分销')), default=False)

    rule = models.SmallIntegerField('下线规则', choices=(
        (0, '首次点击连接'), (1, '首次下单')))
    become = models.SmallIntegerField('成为分销商', choices=(
        (0, '申请'), (1, '不需要申请')))
    minOut = models.DecimalField('最少提现金额', max_digits=5, decimal_places=2, default=0)
    maxOut = models.DecimalField('每日提现上限', max_digits=11, decimal_places=2, default=0)
    charge = models.DecimalField('提现手续费', max_digits=2, decimal_places=2, default=0)

    rate1 = models.DecimalField('一级抽成比率', max_digits=2, decimal_places=2, default=0)
    rate2 = models.DecimalField('二级抽成比率', max_digits=2, decimal_places=2, default=0)
    rate3 = models.DecimalField('三级抽成比率', max_digits=2, decimal_places=2, default=0)

    manua = models.CharField('用户须知', max_length=255)
    agree = models.CharField('申请协议', max_length=255)

    class Meta:
        verbose_name = verbose_name_plural = '配置表'
        db_table = 'invite_conf'


class UidPid(Base):
    """
    用户层级表  F->D->C->B->A
              F  1  2  3
                 D  1  2  3
                    C  1  2
    绑定规则
    1、首次访问绑定：如果是用户主动搜索不进行绑定
    2、首次购买绑定：只要是没绑定过的用户都可以被绑定，分销目的就是推广新用户的，这样子好吗？？？
    """

    uid = models.BigIntegerField('用户ID', primary_key=True)
    pid1 = models.BigIntegerField('第一级ID', blank=True, default=0)
    pid2 = models.BigIntegerField('第二级ID', blank=True, default=0)
    pid3 = models.BigIntegerField('第三级ID', blank=True, default=0)

    status = models.SmallIntegerField('状态', choices=(
        (0, '普通用户'), (1, '分销用户')), default=0)
    created = models.DateTimeField('注册时间')

    class Meta:
        verbose_name = verbose_name_plural = '用户层级表'
        db_table = 'invite_uid_pid'


class UidFee(Base):
    """
    消费记录表, 记录订单金额及当时采用的比率

    rate 记录当时使用抽成比率  0.1,0.03,0.01
    """

    oid = models.BigIntegerField('订单ID', unique=True)
    uid = models.BigIntegerField('用户ID')
    money = models.DecimalField('消费金额', max_digits=11, decimal_places=2, default=0)
    fee1 = models.DecimalField('一级佣金', max_digits=5, decimal_places=2, default=0)
    fee2 = models.DecimalField('二级佣金', max_digits=5, decimal_places=2, default=0)
    fee3 = models.DecimalField('三级佣金', max_digits=5, decimal_places=2, default=0)
    rate = models.CharField('比率记录', max_length=14)
    remark = models.CharField('备注', max_length=50)  # 备注

    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '用户佣金表'
        db_table = 'invite_uid_fee'


class CashOut(Base):
    """
    记录提现, 生成上表时同时创建些表
    """
    rid = models.BigIntegerField('记录ID')
    pid = models.BigIntegerField('用户ID')
    idx = models.SmallIntegerField('级别', choices=(
        (1, '一级'), (2, '二级'), (3, '三级')))
    status = models.SmallIntegerField('状态', choices=(
        (-1, '未成功'), (0, '未提现'), (1, '已提现')), default=0)
    remark = models.CharField('备注', blank=True, null=True, max_length=50)  # 备注未成功原因
    updated = models.DateTimeField('提现时间', null=True, default=None)

    class Meta:
        verbose_name = verbose_name_plural = '提现记录'
        db_table = 'invite_cash_out'
        unique_together = ('rid', 'pid')




