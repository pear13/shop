"""
聚客宝商城系统, 以店铺作为基本管理单元
考虑到用户访问量不太高，使用外键便于开发
为方便管理后台处理，涉及金额使用decimal

一、图片处理：图片先上传保存到图片库->轮播图/首页图->从图库选择

二、商品，规格，库存
规格表具有层级关系，多层级规格构成一个库存约束
查询：spu->sku->spec

三、命名说明
基于数据库的字段、接口参数、接口路径使用小驼峰命令，比下划线少一个字符，节省空间节省流量
快递类命令以ship开头 shipNo, shipFee

四、时间说明
不是每个model都需要 created updated deleted, 有必要才加，像分类/标签就没必要

# 五、foreignKey要修改数据库字段名为小驼峰命名法

六、state表示状态，这个可以来回切换， 而status则是一个流程中的各状态，一旦完成不可更改

七、所有的打印使用 log = logging.getLogger()来打印，不要使用print
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django_mysql.models import JSONField
from ckeditor.fields import RichTextField

from lib import get_save_path


class Base(models.Model):
    """
    saas基础
    """
    appid = models.CharField('小程序appid', max_length=20)

    class Meta:
        abstract = True


class Merc(AbstractUser, Base):
    """
    商户表, 与店铺一一绑定
    """

    avatar = models.ImageField('头像', blank=True, null=True, upload_to=get_save_path, max_length=100)
    phone = models.CharField('手机号', max_length=11)
    birth = models.DateField('生日', blank=True, null=True)

    class Meta:
        verbose_name = verbose_name_plural = '商户'
        db_table = 'jkb_merc'
        unique_together = ['appid']

    def __str__(self):
        return self.username


class Shop(Base):
    """
    商户配置表，只会有一条数据，用来配置用户的相关信息，字典表？

    订单通知，直接开户收款语音播报就好，否则需要另外开通服务号进行推送
    """
    name = models.CharField('商铺名', max_length=30)
    mercId = models.BigIntegerField('商户ID')
    logo = models.ImageField('商户logo', upload_to=get_save_path, max_length=100)
    brief = models.TextField('商铺简介', blank=True, null=True, max_length=2000)
    showBrief = models.BooleanField('显示简介', default=False)

    pushId = models.CharField('消息推送openid', blank=True, null=True, max_length=30)  # 商户个人微信相对于推送服务号的openid

    timeout = models.IntegerField('支付超时时间(分)', default=60)
    useRate = models.BooleanField('启用佣金系统')

    secret = models.CharField('小程序secret', blank=True, null=True, max_length=32)

    mchId = models.CharField('微信商户id', blank=True, null=True, max_length=20)
    mchKey = models.CharField('微信商户key', blank=True, null=True, max_length=32)

    created = models.DateTimeField('入住时间', auto_now_add=True)
    updated = models.DateTimeField('修改时间', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '店铺'
        db_table = 'jkb_shop'
        unique_together = ['appid']

    def __str__(self):
        return self.name


class Staff(Base):
    """
    员工表
    """
    shopId = models.BigIntegerField('店铺ID')
    name = models.CharField('名字', max_length=32)
    role = models.SmallIntegerField('角色', choices=(
        (0, '老板'), (1, '员工')), default=1)
    phone = models.CharField('手机号', max_length=11)
    state = models.SmallIntegerField('状态', choices=(
        (0, '启用'), (1, '禁用')), default=0)

    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '员工表'
        db_table = 'jkb_staff'


class User(Base):
    """
    用户表
    """

    name = models.CharField('用户名', max_length=20)
    avatar = models.URLField('头像', blank=True, null=True, default='')
    phone = models.CharField('手机号', max_length=11, blank=False, null=True, default=None)
    birth = models.DateField('生日', blank=True, null=True)
    sex = models.BooleanField('性别', blank=True, null=True, default=None)

    openid = models.CharField('openid', blank=True, null=True, max_length=32)
    unionid = models.CharField('unionid', blank=True, null=True, max_length=20)

    apikey = models.CharField('接口密钥', max_length=32)  # 创建时需要默认生成

    class Meta:
        verbose_name = verbose_name_plural = '用户表'
        db_table = 'jkb_user'
        unique_together = ('appid', 'openid')

    def __str__(self):
        return self.name


class Brand(Base):
    """
    品牌表
    """
    name = models.CharField('品牌名称', unique=True, max_length=20)
    logo = models.ImageField('品牌图片', upload_to=get_save_path, max_length=100)
    desc = RichTextField('品牌介绍', max_length=2000)

    class Meta:
        verbose_name = verbose_name_plural = '品牌'

        db_table = 'jkb_brand'

    def __str__(self):
        return self.name


class Cate(Base):
    """
    分类表
    """

    name = models.CharField('分类', unique=True, max_length=20)
    pid = models.BigIntegerField('父类id', default=0)
    cnt = models.BigIntegerField('商品数', default=0)
    cover = models.ImageField('图片', blank=True, null=True, default=None)

    class Meta:
        verbose_name = verbose_name_plural = '分类'

        db_table = 'jkb_cate'

    def __str__(self):
        return self.name


class Cate2(Cate):
    """仅管理端使用"""
    class Meta:
        proxy = True
        verbose_name = verbose_name_plural = '二级分类'


class Tag(Base):
    """
    商品标签表
    """
    name = models.CharField('标签', unique=True, max_length=20)
    cnt = models.BigIntegerField('商品数', default=0)
    remark = models.CharField('备注', blank=True, null=True, max_length=200)

    class Meta:
        verbose_name = verbose_name_plural = '标签'

        db_table = 'jkb_tag'

    def __str__(self):
        return self.name


class Ship(Base):
    """
    运费规则

    省份为空时为所有省默认，
    """

    name = models.CharField('规则名称', max_length=20)
    shipType = models.SmallIntegerField('计费类型', choices=(
        (0, '按件计费'), (1, '按重量计费'), (3, '免邮')
    ), default=0)
    iniFee = models.DecimalField('起始费用', max_digits=11, decimal_places=2, blank=True, default=0)
    iniWei = models.DecimalField('起始重量', max_digits=5, decimal_places=2, blank=True, default=0)
    addFee = models.DecimalField('增加费用', max_digits=11, decimal_places=2, blank=True, default=0)
    addWei = models.DecimalField('增加重量', max_digits=5, decimal_places=2, blank=True, default=0)
    default = models.BooleanField('默认', default=False)

    class Meta:
        verbose_name = verbose_name_plural = '运费规则'
        unique_together = ('appid', 'name')
        db_table = 'jkb_ship'

    def __str__(self):
        return self.name


class ShipProv(Base):
    """
    指定省份运费规则
    """
    shipId = models.BigIntegerField('运费规则ID')
    provId = models.IntegerField('省份ID')
    iniFee = models.DecimalField('起始费用', max_digits=11, decimal_places=2, blank=True, default=0)
    iniWei = models.DecimalField('起始重量', max_digits=5, decimal_places=2, blank=True, default=0)
    addFee = models.DecimalField('增加费用', max_digits=11, decimal_places=2, blank=True, default=0)
    addWei = models.DecimalField('增加重量', max_digits=5, decimal_places=2, blank=True, default=0)

    class Meta:
        verbose_name = verbose_name_plural = '指定省份运费规则'
        unique_together = ('appid', 'shipId', 'provId')
        db_table = 'jkb_ship_prov'


class Spu(Base):
    """
    标准商品单元，存放不影响商品价格的属性
    """
    title = models.CharField('商品名', max_length=30)
    subtitle = models.CharField('副标题', blank=True, null=True, max_length=50)
    cover = models.ImageField('封面图', upload_to=get_save_path, max_length=100)
    video = models.ImageField('视频', upload_to=get_save_path, max_length=100, blank=True)
    brandId = models.BigIntegerField('品牌ID')
    cateId = models.BigIntegerField('分类ID')
    sales = models.IntegerField('总销量', default=0)
    cmtCnt = models.IntegerField('总评论', default=0)  # 冗余数据，便于查询处理
    shipId = models.BigIntegerField('运费规则ID')
    created = models.DateTimeField('创建时间', auto_now_add=True)
    updated = models.DateTimeField('修改时间', auto_now=True)

    vipSee = models.SmallIntegerField('会员可见', choices=(
        (-1, "非会员可见"), (0, '所有可见'), (1, '会员可见')
    ), default=0)

    state = models.SmallIntegerField('状态', choices=(
        (0, '未上架'), (1, '上架中')
    ), default=0)

    class Meta:
        verbose_name = verbose_name_plural = '商品单元'

        db_table = 'jkb_spu'

    def __str__(self):
        return self.title


class SpuContent(Base):
    """图文详情"""

    spuId = models.BigIntegerField('SpuID')
    image = models.ImageField('图片', blank=True, default='')
    video = models.FileField('视频', blank=True, default='')
    text = models.CharField('文本', blank=True, null=True, max_length=500)

    class Meta:
        verbose_name = verbose_name_plural = '图文详情'
        db_table = 'jkb_spu_content'

    def __str__(self):
        return f'图文{self.id}'


class SpuServ(Base):
    """保障服务， 7天包退， 7天可换 24小时发货"""
    serv = models.SmallIntegerField('服务', choices=(
        (0, '7天包退'), (1, '7天可换'), (2, '24小时发货')), default=2)
    spuId = models.BigIntegerField('SpuID')

    class Meta:
        verbose_name = verbose_name_plural = '保障服务'
        db_table = 'jkb_spu_serv'
        unique_together = ('appid', 'spuId', 'serv')

    def __str__(self):
        return str(self.id)


class SpuTag(Base):
    """
    商品标签关联表
    """
    spuId = models.BigIntegerField('SpuID')
    tagId = models.BigIntegerField('标签ID')

    class Meta:
        verbose_name = verbose_name_plural = '商品标签关联表'
        db_table = 'jkb_spu_tag'

        unique_together = ('appid', 'spuId', 'tagId')


class Favor(Base):
    """
    收藏表， 可以是商品也可以是其他
    """

    userId = models.BigIntegerField('用户ID')
    objId = models.BigIntegerField('对象ID')
    objType = models.SmallIntegerField('对象类型', choices=(
        (0, '商品'), ), default=0)

    class Meta:
        verbose_name = verbose_name_plural = '收藏表'
        db_table = 'jkb_favor'

        unique_together = ('appid', 'userId', 'objId', 'objType')


class Sku(Base):
    """
    标准库存单元, 一经创建不许修改, 防止已经生成的订单属性被修改变更
    """
    cover = models.ImageField('封面图', max_length=100)
    market = models.DecimalField('划线价/市场价', max_digits=11, decimal_places=2)
    price = models.DecimalField('标价', max_digits=11, decimal_places=2)
    cost = models.DecimalField('成本价', max_digits=11, decimal_places=2)
    stock = models.IntegerField('库存')
    spuId = models.BigIntegerField('SpuID')
    weight = models.DecimalField('重量', max_digits=4, decimal_places=1, default=0)
    buyMax = models.SmallIntegerField('最大购买量', default=0)  # 0为不限制

    class Meta:
        verbose_name = verbose_name_plural = '库存单元'

        db_table = 'jkb_sku'

    def __str__(self):
        return str(self.id)


class AttrName(Base):
    """定义商品有几个属性"""
    spuId = models.BigIntegerField('spuID')
    name = models.CharField('属性名', max_length=20)
    pid = models.BigIntegerField('上级属性ID')

    class Meta:
        verbose_name = verbose_name_plural = '属性名'
        db_table = 'jkb_attr_name'
        unique_together = ('appid', 'spuId', 'name')

    def __str__(self):
        return self.name


class AttrValue(Base):
    """定义sku对应每个属性的值"""
    skuId = models.BigIntegerField('skuID')
    attId = models.BigIntegerField('属性名ID')
    value = models.CharField('属性值', max_length=50)  # 属性值都处理成字符串

    class Meta:
        verbose_name = verbose_name_plural = '属性值'
        db_table = 'jkb_attr_value'
        unique_together = ('appid', 'skuId', 'attId', 'value')

    def __str__(self):
        return self.value


class Spec(Base):
    """
    规格表，目前只考虑影响价格的属性。后期可能添加不影响价格的属性，直接绑定spu

    当前系统的商品不会有太多属性层级，一个商品sku不多，展示时将所有sku数据返回，前端处理过滤

    使用拼多多的方式，目前淘宝京东抓不到对应接口, 淘宝貌似类似
    首次进入使用商品的图片与数量使用商品的图片与数量，文本设置提示选择

    作为商品详情的子数据项

    goodDetail{
        商品其他参数
        skus:[
            {
                quantity: 123,
                attrs: [
                    {'attr1': 'value1'},
                    {'attr2': 'value2'},
                    {'attr3': 'value3'},
                    ...
                ],
                其他sku参数
            },
            ...
        ]
        ...
    }

    后端取法:
    1、gooid取所有sku
    2、根据级联关系一次按顺序取出所有属性
    ...

    Spec.objects.filter(sku=sku).sortBy('pid')

    前端需要根据返回的sku列表处理显示细节，如暗掉没有数据有对应项
    """

    attr = models.CharField('规格', max_length=20)
    value = models.CharField('属性值', max_length=20)
    pid = models.BigIntegerField('上级规格ID', default=0)

    skuId = models.BigIntegerField('SkuID')

    class Meta:
        verbose_name = verbose_name_plural = '规格'

        db_table = 'jkb_spec'

    def __str__(self):
        return self.attr


class Img(Base):
    """
    我的图库
    """

    image = models.ImageField('图片地址', upload_to=get_save_path, max_length=100)

    class Meta:
        verbose_name = verbose_name_plural = '我的图库'

        db_table = 'jkb_img'


class SpuImg(Base):
    """
    商品轮播图
    """

    image = models.ImageField('图片', upload_to=get_save_path)
    spuId = models.BigIntegerField('SpuID')

    class Meta:
        verbose_name = verbose_name_plural = '商品轮播图'

        db_table = 'jkb_spu_img'

    def __str__(self):
        return str(self.id)


class HomeImg(Base):
    """
    首页轮播图配置
    """

    image = models.ImageField('图片')
    imgType = models.SmallIntegerField('图片类型', choices=(
        (0, '海报'), (1, '商品'), (2, '活动页')), default=0)
    idpath = models.CharField('商品ID或连接', max_length=100, blank=True, null=True, default='')

    class Meta:
        verbose_name = verbose_name_plural = '首页轮播图'
        db_table = 'jkb_home_img'

    def __str__(self):
        return str(self.id)


class HomeCate(Base):
    """
    首页分类配置
    """

    cateId = models.BigIntegerField('分类ID')
    index = models.SmallIntegerField('分类顺序', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '首页分类配置'
        db_table = 'jkb_home_cate'
        unique_together = ('appid', 'cateId')

    def __str__(self):
        return str(self.id)


class Cart(Base):
    """
    购物车
    """

    userId = models.BigIntegerField('用户ID')
    skuId = models.BigIntegerField('SkuID')
    amount = models.IntegerField('数量')

    class Meta:
        verbose_name = verbose_name_plural = '购物车'
        db_table = 'jkb_cart'


class Order(Base):
    """
    订单表
    """

    orderNo = models.CharField('订单号', unique=True, max_length=20)
    tradeNo = models.CharField('交易号', unique=True, blank=True, null=True, max_length=20)
    userId = models.BigIntegerField('用户ID')
    status = models.SmallIntegerField('订单状态', choices=(
        (0, '待付款'),
        (1, '待发货'),
        (2, '待收货'),
        (3, '已完成'),
        (4, '已关闭')  # 已关闭的不能再进行操作且回滚库存，取消订单/支付超时
    ), default=0)
    remark = models.CharField('备注', blank=True, null=True, max_length=100)

    payType = models.SmallIntegerField('支付方式', choices=((0, '微信支付'), (1, '银行卡')), default=0)

    totalFee = models.DecimalField('总金额', max_digits=11, decimal_places=2)
    realFee = models.DecimalField('实付金额', max_digits=11, decimal_places=2)
    coupFee = models.DecimalField('优惠金额', max_digits=11, decimal_places=2)

    shipFee = models.DecimalField('快递费', max_digits=11, decimal_places=2)
    shipNo = models.CharField('快递单号', blank=True, null=True, max_length=30)

    name = models.CharField('收件人', max_length=10)
    phone = models.CharField('收件人手机号', max_length=11)
    address = models.CharField('收货地址', max_length=255)

    isRefund = models.BooleanField('是否退款', default=False)
    isComment = models.BooleanField('已评论', default=False)
    isClose = models.BooleanField('订单关闭', default=False)  # 支付超时时关闭并释放库存

    score = models.IntegerField('所得积分', default=0)

    created = models.DateTimeField('下单时间', auto_now_add=True)
    payTime = models.DateTimeField('支付时间', blank=True, null=True)
    sendTime = models.DateTimeField('发货时间', blank=True, null=True)
    takeTime = models.DateTimeField('收货时间', blank=True, null=True)

    payNoti = models.SmallIntegerField('支付通知状态', choices=(
        (0, '未通知'), (1, '通知成功'), (2, '通知失败'), (3, '查询支付成功')
    ), default=0)
    pushed = models.BooleanField('下单通知商户', default=False)

    updated = models.DateTimeField('修改时间', auto_now=True)
    deleted = models.DateTimeField('删除时间', blank=True, null=True)  # 用户删除时不是真删除，只是加了删除时间

    class Meta:
        verbose_name = verbose_name_plural = '订单表'

        db_table = 'jkb_order'

    def __str__(self):
        return self.orderNo


class OrderSku(Base):
    """
    订单商品表
    """

    orderId = models.BigIntegerField('订单ID')
    skuId = models.BigIntegerField('skuID')
    amount = models.IntegerField('数量')
    shipFee = models.BigIntegerField('快递费', default=0)
    price = models.DecimalField('价格', max_digits=11, decimal_places=2)
    weight = models.DecimalField('重量', max_digits=4, decimal_places=1, default=0)

    class Meta:
        verbose_name = verbose_name_plural = '订单商品表'
        db_table = 'jkb_order_sku'

    def __str__(self):
        return str(self.id)


class OrderSkuRefund(Base):
    """
    订单售后表，兼退款与换货
    """

    orderSkuId = models.BigIntegerField('订单SkuID')
    refundType = models.SmallIntegerField('售后类型', choices=(
        (0, '仅退款'), (1, '退货退款'), (2, '换货')), default=0)
    refundNo = models.CharField('退款流水号', max_length=20)  # 直接用订单号+'1', 用于向微信发起申请
    refundFee = models.DecimalField('退款金额', max_digits=11, decimal_places=2)
    reason = models.SmallIntegerField('退款原因', choices=(
        (0, '不合适'), (1, '不喜欢'), (2, '买错了')
    ), default=0)
    remark = models.CharField('退款备注', blank=True, null=True, max_length=200)
    status = models.SmallIntegerField('退款状态', choices=(
        (0, '等待商家处理'), (1, '已处理')
    ), default=0)
    created = models.DateTimeField('申请时间', auto_now_add=True)
    refundTime = models.DateTimeField('退款时间', blank=True, null=True)
    shipNo = models.CharField('快递单号', blank=True, null=True, max_length=32)

    class Meta:
        verbose_name = verbose_name_plural = '订单售后表'
        db_table = 'jkb_order_sku_refund'

    def __str__(self):
        return str(self.id)


class RefundImg(Base):
    """退货凭证"""

    image = models.ImageField('图片')
    orderSkuId = models.BigIntegerField('订单SkuID')

    class Meta:
        verbose_name = verbose_name_plural = '退货凭证'
        db_table = 'jkb_refund_img'

    def __str__(self):
        return str(self.id)


class SpuCmt(Base):
    """
    商品评论表
    """

    userId = models.BigIntegerField('用户ID')
    userType = models.SmallIntegerField('用户类型', choices=(
        (0, '客户'), (1, '商家')), default=0)
    spuId = models.BigIntegerField('spuID')
    orderId = models.BigIntegerField('订单ID')
    content = models.CharField('评论内容', max_length=300)
    replyTo = models.BigIntegerField('回复评论ID', default=0)
    status = models.SmallIntegerField('状态', choices=(
        (-1, '不通过'), (0, '未审核'), (1, '通过')
    ), default=0)

    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '商品评论表'

        db_table = 'jkb_spu_cmt'

    def __str__(self):
        return str(self.id)


class CmtImg(Base):
    """
    评论图片
    """
    image = models.ImageField('图片')
    spuCmtId = models.BigIntegerField('评论ID')

    class Meta:
        verbose_name = verbose_name_plural = '评论图片'
        db_table = 'jkb_cmt_img'

    def __str__(self):
        return str(self.id)


class TagCmt(Base):
    """
    评论标签
    """
    name = models.CharField('评论标签名', unique=True, max_length=20)
    cnt = models.BigIntegerField('评论数', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '评论标签'
        db_table = 'jkb_tag_cmt'

    def __str__(self):
        return self.name


class SpuCmtTag(Base):
    """
    评论标签关联表
    """

    spuCmtId = models.BigIntegerField('评论ID')
    tagCmtId = models.BigIntegerField('评论标签ID')

    class Meta:
        verbose_name = verbose_name_plural = '评论标签关联表'
        db_table = 'jkb_spu_cmt_tag'

    def __str__(self):
        return str(self.id)


class District(models.Model):
    """
    行政区域表
    """
    id = models.BigIntegerField('编码', primary_key=True)
    name = models.CharField('名字', max_length=30)
    pid = models.BigIntegerField('上级编码')

    class Meta:
        verbose_name = verbose_name_plural = '行政区域表'
        db_table = 'jkb_district'

    def __str__(self):
        return self.name


class Addr(Base):
    """
    地址表
    """

    userId = models.BigIntegerField('用户ID')
    userType = models.SmallIntegerField('用户类型', choices=((0, '用户'), (1, '商户')), default=0)
    name = models.CharField('收货人', max_length=10)
    phone = models.CharField('手机号', max_length=11)
    provId = models.IntegerField('省')  # 嵌套表不能用foreignkey
    cityId = models.IntegerField('市')
    areaId = models.IntegerField('区')
    detail = models.CharField('详细地址', max_length=255)
    default = models.BooleanField('默认', default=False)
    lng = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)
    lat = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    useTime = models.DateTimeField('最后使用时间', blank=True, null=True)  # 可用于取最近使用地址
    created = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '地址表'
        db_table = 'jkb_addr'

    def __str__(self):
        return str(self.id)


class LogSms(Base):
    """
    短信发送记录, 暂时不使用
    """

    type = models.BooleanField('系统消息', default=False)
    mercId = models.BigIntegerField('商户ID')
    content = models.CharField('消息内容', max_length=100)  # 可忽略
    phone = models.CharField('手机号', max_length=11)
    code = models.CharField('验证码', max_length=6)
    created = models.DateTimeField('申请时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '短信记录'
        db_table = 'jkb_log_sms'


class Activity(Base):
    """
    活动, 过段时间可能会出一期活动，券规则
    """

    title = models.CharField('活动标题', max_length=30)
    poster = models.ImageField('活动海报', upload_to=get_save_path, max_length=100)  # 活动页背影图
    rules = models.CharField('活动规则', max_length=300)
    beginTime = models.DateField('开始时间')
    closeTime = models.DateField('结束时间')
    state = models.SmallIntegerField('活动状态', choices=(
        (0, '下线'), (1, '上线')
    ), default=0)

    class Meta:
        verbose_name = verbose_name_plural = '活动'
        db_table = 'jkb_activity'


class CoupInfo(Base):
    """
    用户领取分直接发送/点击领取

    审核通过后提前按配置生成券，活动过期后清理未领取的券
    """
    total = models.BigIntegerField('发行数量')
    pickNum = models.BigIntegerField('领取数量')
    usedNum = models.BigIntegerField('使用数量')
    title = models.CharField('优惠券名称', max_length=30)
    subtitle = models.CharField('优惠券副标题', max_length=50)
    coupType = models.SmallIntegerField('优惠类型', choices=(
        (0, '现金券'), (1, '满减券'),  # (2, '折扣券') 这个先不加
    ), default=0)
    manual = models.CharField('使用说明', max_length=255)
    isFix = models.BooleanField('固定金额', default=True)
    minFee = models.DecimalField('最小金额', max_digits=5, decimal_places=2, default=0)  # 固定金额时取最小金额
    maxFee = models.DecimalField('最大金额', max_digits=5, decimal_places=2, default=0)

    period = models.DurationField('有效期')  # 从领取时算起

    sendType = models.SmallIntegerField('发放类型', choices=(
        (0, '注册送券'),
        (1, '邀请送券'),  # 邀请用户注册成功后发送
        (2, '活动送券'),  # 节假日促销活动发送
        (3, '分享送券'),  # 下单后分享给好友送券
        (4, '主动送券'),  # 为刺激留存用户，唤醒沉睡用户，以短消息形式推送
        (5, '会员送券'),  # 类似饿了么会员每月有20元无门槛红包
        (6, '购买赠送')
    ), default=0)

    isMutex = models.BooleanField('互斥券', default=True)
    level = models.SmallIntegerField('优先级', default=0)
    getFee = models.DecimalField('消费满可获得', max_digits=5, decimal_places=2, default=0)
    useFee = models.DecimalField('最低消费可用', max_digits=11, decimal_places=2, default=0)

    status = models.SmallIntegerField('审核状态', choices=(
        (0, '待审核'), (1, '审核通过')))

    activityId = models.BigIntegerField('活动ID')

    class Meta:
        verbose_name = verbose_name_plural = '优惠券信息'
        db_table = 'jkb_coup_info'

    def __str__(self):
        return self.title


class Coupon(Base):
    """
    优惠券
    """
    infoId = models.BigIntegerField('优惠券信息ID', default=0)
    money = models.DecimalField('优惠金额', max_digits=5, decimal_places=2, default=0)
    status = models.SmallIntegerField('状态', choices=(
        (0, '领取未使用'), (1, '已使用'), (2, '已过期')
    ), default=0)
    useTime = models.DateTimeField('使用时间', blank=True, null=True)
    expired = models.DateTimeField('过期时间', blank=True, null=True)
    created = models.DateTimeField('领取时间', blank=True, null=True)

    userId = models.BigIntegerField('用户ID', null=True, default=None)
    orderId = models.BigIntegerField('订单ID', null=True, default=None)

    class Meta:
        verbose_name = verbose_name_plural = '优惠券'
        db_table = 'jkb_coupon'

    def __str__(self):
        return str(self.id)


class UserPids(Base):
    """
    用户层级表  F->D->C->B->A
              F  1  2  3
                 D  1  2  3
    绑定规则
    1、首次访问绑定：如果是用户主动搜索不进行绑定
    2、首次购买绑定：只要是没绑定过的用户都可以被绑定，分销目的就是推广新用户的，这样子好吗？？？
    """

    userId = models.BigIntegerField('用户ID')
    pid1 = models.BigIntegerField('第一级', blank=True, default=0)
    pid2 = models.BigIntegerField('第二级', blank=True, default=0)
    pid3 = models.BigIntegerField('第三级', blank=True, default=0)

    class Meta:
        verbose_name = verbose_name_plural = '用户层级表'
        db_table = 'jkb_user_pids'


class Event(Base):
    """
    小程序用户事件日志，待定义完整
    """

    userId = models.BigIntegerField('用户ID')
    type = models.SmallIntegerField('事件类型', choices=(
        (0, '新用户访问'),
        (1, '页面访问'),
        (2, '点击'),
    ))

    path = models.CharField('访问路径', max_length=50)
    created = models.DateTimeField('发生时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '小程序事件日志'
        db_table = 'jkb_event'


class PageConf(Base):
    """
    小程序界面配置, 是否需要根据路径来配置，还是只存储一个配置即可？
    """
    path = models.CharField('路径', max_length=100)
    conf = JSONField('json')

    class Meta:
        verbose_name = verbose_name_plural = '界面配置'
        db_table = 'jkb_page_conf'
        index_together = ('appid', )


###############################################################################
# 分享相关表
###############################################################################

class ShareQrcode(models.Model):
    """
    spuId为0时为分享整个小程序，不为0时分享
    """

    image = models.URLField('qrcode', max_length=100)
    userId = models.BigIntegerField('用户ID', default=0)
    spuId = models.BigIntegerField('商品ID', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '测试注册'
        db_table = 'share_qrcode'
        unique_together = ('userId', 'spuId')


class ShareMark(Base):
    """分享标志, 纯id生成"""

    markType = models.SmallIntegerField('分享类型', choices=(
        (0, '分享小程序'), (1, '分享商品')), default=0)

    class Meta:
        verbose_name = verbose_name_plural = '分享标志'
        db_table = 'share_mark'


class ShareRecord(Base):
    """

    """
    markId = models.BigIntegerField('分享标志')
    userId = models.BigIntegerField('用户ID')
    shareBy = models.BigIntegerField('邀请人ID')
    created = models.DateTimeField('点击时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '分享记录'
        db_table = 'share_record'



# #############################################################################
# # 会员相关定义
# class VipInfo(Base):
#     userId = models.BigIntegerField('用户ID')
#     level = models.SmallIntegerField('会员等级')
#
#
#
# #############################################################################
# # 分销相关定义