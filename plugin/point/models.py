from django.db import models

from main.models import Base


class ScoreRule(Base):
    """积分规则"""

    ruleType = models.SmallIntegerField('类型', choices=(
        (0, '每消费1元'), (1, '每交易1单')))
    score = models.SmallIntegerField('得分')

    class Meta:
        verbose_name = verbose_name_plural = '积分记录表'
        db_table = 'score_rule'


class ScoreRank(Base):
    userId = models.BigIntegerField('用户ID')
    total = models.IntegerField('总积分')
    rank = models.SmallIntegerField('等级')

    class Meta:
        verbose_name = verbose_name_plural = '得分等级榜'
        db_table = 'score_rank'


class ScoreAdd(Base):
    """
    如果涉及部分退款, 则需要同步更新
    """
    userId = models.BigIntegerField('用户ID')
    orderId = models.BigIntegerField('订单ID')
    orderFee = models.IntegerField('订单金额')
    score = models.IntegerField('所得积分')
    remark = models.CharField('使用规则说明', max_length=50)  # 比如消费1元得1分，主要避免后期改规则引起错乱
    created = models.DateTimeField('获得时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '消费积分表'
        db_table = 'score_add'


class ScoreGift(Base):
    """
    积分礼品表
    """

    cover = models.ImageField('封面图')
    title = models.CharField('商品名', max_length=100)
    price = models.DecimalField('价格', max_digits=11, decimal_places=2, default=0)
    score = models.IntegerField('积分')
    stock = models.IntegerField('库存', blank=True, default=0)
    state = models.BooleanField('状态', choices=((0, '下架'), (1, '上架')), default=0)
    excMax = models.SmallIntegerField('最大兑换数量', default=1)  # 0表示不限量
    share = models.CharField('分享文案', max_length=200)

    class Meta:
        verbose_name = verbose_name_plural = '积分礼品表'
        db_table = 'score_gift'

    def __str__(self):
        return self.title


class ScoreExc(Base):

    userId = models.BigIntegerField('用户ID')
    giftId = models.BigIntegerField('商品ID')
    number = models.IntegerField('兑换数量')

    class Meta:
        verbose_name = verbose_name_plural = '积分兑换表'
        db_table = 'score_exc'


