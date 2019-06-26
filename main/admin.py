# 商户的表访问权限通过用户组来过滤
# 对于一些字段的修改访问特性还是需要用get_queryset单独设置

from django.contrib import admin
from django.db.models import Max, Min, Sum, Count, F, Q, Value, Subquery, OuterRef
from django.db.models import IntegerField, DecimalField
from django.db.models.expressions import RawSQL
from django.db import models

from .models import *
from .forms import *
from lib import show_img


class BaseAdmin(admin.ModelAdmin):
    """
    普通用户自动获取appid写入
    """

    # list_display_links = None  # 禁用所有连接, 使用自定义option

    def save_model(self, request, obj, form, change):
        """保存时默认存储appid"""

        if not obj.appid:
            obj.appid = request.user.appid
        # if not request.user.is_superuser:
        #     obj.appid = request.user.appid
        super(BaseAdmin, self).save_model(request, obj, form, change)

    def get_queryset(self, request):
        """查询时默认过虑appid"""
        query = super(BaseAdmin, self).get_queryset(request)
        user = request.user
        if not user.is_superuser:
            query = query.filter(appid=user.appid)
        return query

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """外键数据过滤, 注意外键必须是类的小写，且只能是一个单词"""

        kwargs["queryset"] = eval(db_field.name.capitalize()).objects.filter(appid=request.user.appid)
        return super(BaseAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_exclude(self, request, obj=None):
        """商户不显示appid"""
        return [] if request.user.is_superuser else ['appid']


@admin.register(Shop)
class ShopAdmin(BaseAdmin):
    search_fields = ['name']
    exclude = ['mercId']


@admin.register(Merc)
class MercAdmin(BaseAdmin):
    list_display = ('id', 'appid', 'username', 'phone', 'birth', 'show_avatar')
    search_fields = ['username']
    readonly_fields = ('last_login', 'date_joined')
    exclude = ('password',)

    def get_queryset(self, request):
        return super(MercAdmin, self).get_queryset(request)

    def show_avatar(self, obj):
        return show_img(obj.avatar)

    show_avatar.short_description = '头像'

    def get_changeform_initial_data(self, request):
        """初始化表单值"""
        ini = super(MercAdmin, self).get_changeform_initial_data(request)
        ini['appid'] = ini.get('appid', request.user.appid)
        return ini


@admin.register(Img)
class ImgAdmin(BaseAdmin):
    readonly_fields = ['appid']

    def get_list_display(self, request):  # 选择显示列
        if request.user.is_superuser:
            return ['id', 'get_img', 'appid']
        else:
            return ['id', 'get_img']

    def get_queryset(self, request):
        query = super(ImgAdmin, self).get_queryset(request)
        if not request.user.is_superuser:
            query = query.filter(appid=request.user.appid)
        return query

    def get_img(self, obj):
        return show_img(obj.image, w=80, h=80)

    get_img.short_description = '图片'

    # 保存前添加默认属性
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.appid = request.user.appid
        super(ImgAdmin, self).save_model(request, obj, form, change)


@admin.register(Brand)
class BrandAdmin(BaseAdmin):
    list_display = ('id', 'name', 'get_logo', 'desc')
    search_fields = ['name']

    def get_logo(self, obj):
        return show_img(obj.logo, w=64, h=64)

    get_logo.short_description = 'logo'


@admin.register(Cate)
class CateAdmin(BaseAdmin):
    list_display = ('id', 'name', 'cnt')
    search_fields = ['name']
    readonly_fields = ['cnt']
    list_per_page = 5

    def cate_cnt(self, obj):
        return obj.sub_cnt

    def get_queryset(self, request):
        return super(CateAdmin, self).get_queryset(request).filter(pid=0)

    def get_exclude(self, request, obj=None):
        exc = super(CateAdmin, self).get_exclude(request, obj)
        exc.append('pid')
        return exc


@admin.register(Cate2)
class Cate2Admin(BaseAdmin):
    form = Cate2Form

    list_display = ('id', 'name', 'cate_name', 'cnt')
    search_fields = ['name', 'cate_name']
    readonly_fields = ['cnt']

    def cate_name(self, obj):
        return obj.cate_name

    cate_name.short_description = '父分类'

    # def get_queryset(self, request):
    #     return super(Cate2Admin, self).get_queryset(request).exclude(pid=0)
    def get_queryset(self, request):
        print(request.user.appid)
        return super(Cate2Admin, self).get_queryset(request).exclude(pid=0).annotate(
            cate_name=Subquery(Cate.objects.filter(id=OuterRef('pid')).values('name')[:1]))

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.pid = form.cleaned_data['cate'].id
        else:
            obj.pid = 0
        super(Cate2Admin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(Cate2Admin, self).get_form(request, obj, change, **kwargs)
        query = Cate.objects.filter(appid=request.user.appid)
        form.base_fields['cate'].queryset = query
        if obj:
            form.base_fields['cate'].initial = query.filter(id=obj.pid).first()
        return form


@admin.register(Spu)
class SpuAdmin(BaseAdmin):
    # list_display = ['title', 'cate_name', 'get_price', 'get_tags', 'get_stock', 'sales', 'created', 'state']
    list_display = ['title', 'cate_name', 'get_price', 'get_tags', 'get_stock', 'sales', 'created', 'state']
    radio_fields = {'vipSee': admin.HORIZONTAL, 'state': admin.HORIZONTAL}
    readonly_fields = ['created', 'updated', 'sales', 'cmtCnt']

    search_fields = ['title', 'cate_name']

    # change_form_template = "change_spu_sku.html"

    form = SpuForm

    fieldsets = (
        ('基本信息', {
            'fields': ['state', 'title', 'cover', 'video', 'cate', 'ship', 'vipSee']
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(SpuAdmin, self).get_form(request, obj, change, **kwargs)
        query1 = Cate.objects.filter(appid=request.user.appid)
        query2 = Ship.objects.filter(appid=request.user.appid)
        form.base_fields['cate'].queryset = query1
        form.base_fields['ship'].queryset = query2
        if obj:
            form.base_fields['cate'].initial = Cate.objects.filter(id=obj.cateId).first()
            form.base_fields['ship'].initial = Cate.objects.filter(id=obj.shipId).first()
        return form

    def get_price(self, obj):
        if obj.min_price == obj.max_price:
            return obj.min_price or 0
        return f'{obj.min_price}~{obj.max_price}'

    get_price.short_description = '价格'

    def get_stock(self, obj):
        return obj.all_stock or 0

    get_stock.short_description = '总库存'

    def get_tags(self, obj):
        return obj.tag_1line

    get_tags.short_description = '标签'

    def cate_name(self, obj):
        return obj.cate_name

    cate_name.short_description = '分类'

    def get_queryset(self, request):
        return super(SpuAdmin, self).get_queryset(request).annotate(
            cate_name=Subquery(Cate.objects.filter(id=OuterRef('cateId'), appid=OuterRef('appid')).values('name')[:1]),
            min_price=Subquery(
                Sku.objects.filter(spuId=OuterRef('pk')).annotate(minfee=Min('price')).values('minfee')[:1]),
            max_price=Subquery(
                Sku.objects.filter(spuId=OuterRef('pk')).annotate(maxfee=Max('price')).values('maxfee')[:1]),
            all_stock=Subquery(
                Sku.objects.filter(spuId=OuterRef('pk')).annotate(stocks=Sum('stock')).values('stocks')[:1]),
            tag_1line=RawSQL(
                "select group_concat(t.name separator ', ') from jkb_spu_tag st left join jkb_tag t on st.tagId=t.id where spuId=jkb_spu.id",
                params=[])
        )

    def save_model(self, request, obj, form, change):
        if not change:
            Cate.objects.filter(id=obj.cateId).update(cnt=F('cnt') + 1)
        return super(SpuAdmin, self).save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        Cate.objects.filter(id=obj.cateId).update(cnt=F('cnt') - 1)
        return super(SpuAdmin, self).delete_model(request, obj)

    class Media:
        js = ('spu_sku.js',)


@admin.register(Tag)
class TagAdmin(BaseAdmin):
    """

    """
    list_display = ('id', 'name', 'cnt', 'remark')
    search_fields = ['name']
    readonly_fields = ['cnt']
    list_per_page = 5


@admin.register(SpuTag)
class SpuTagAdmin(BaseAdmin):
    """
    商品标签关联表
    """
    list_display = ('tag_name', 'spu_title')
    search_fields = ['tag_name', 'spu_title']
    # readonly_fields = ('spuId', 'tagId')
    form = SpuTagForm

    def tag_name(self, obj):
        return obj.tag_name

    tag_name.short_description = '标签名'

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品名'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(SpuTagAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]),
            tag_name=Subquery(Tag.objects.filter(id=OuterRef('tagId')).values('name')[:1]),
        )

    # def save_model(self, request, obj, form, change):
    #     if form.is_valid():
    #         obj.pid = form.cleaned_data['cate'].id
    #     else:
    #         obj.pid = 0
    #     super(Cate2Admin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        print(request.user.appid)
        form = super(SpuTagAdmin, self).get_form(request, obj, change, **kwargs)
        query1 = Spu.objects.filter(appid=request.user.appid)
        query2 = Tag.objects.filter(appid=request.user.appid)
        form.base_fields['title'].queryset = query1
        form.base_fields['name'].queryset = query2
        if obj:
            form.base_fields['title'].initial = Spu.objects.filter(id=obj.spuId).first()
            form.base_fields['name'].initial = Tag.objects.filter(id=obj.TagId).first()
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            Tag.objects.filter(id=obj.tagId).update(cnt=F('cnt') + 1)

        if form.is_valid():
            obj.spuId = form.cleaned_data['title'].id
            obj.tagId = form.cleaned_data['name'].id
        else:
            obj.spuId = 0
            obj.tagId = 0
        return super(SpuTagAdmin, self).save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        Tag.objects.filter(id=obj.tagId).update(cnt=F('cnt') - 1)
        return super(SpuTagAdmin, self).delete_model(request, obj)


@admin.register(Sku)
class SkuAdmin(BaseAdmin):
    list_display = ['spu_title', 'show_cover', 'price', 'stock']
    search_fields = ['spu_title', 'price', 'stock']
    # readonly_fields = ['spuId']
    form = SkuForm

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品名'

    def show_cover(self, obj):
        return show_img(obj.cover, w=64, h=64)

    show_cover.short_description = '封面图'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(SkuAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]))

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.spuId = form.cleaned_data['title'].id
        else:
            obj.spuId = 0
        super(SkuAdmin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(SkuAdmin, self).get_form(request, obj, change, **kwargs)
        query = Spu.objects.filter(appid=request.user.appid)
        form.base_fields['title'].queryset = query
        if obj:
            form.base_fields['title'].initial = Spu.objects.filter(id=obj.spuId).first()
        return form


@admin.register(Spec)
class SpecAdmin(BaseAdmin):
    list_display = ['id', 'attr', 'value', 'pid', 'skuId']
    list_display_links = None
    pass


@admin.register(Ship)
class ShipAdmin(BaseAdmin):
    form = ShipForm

    list_display = ['name', 'shipType', 'iniFee', 'iniWei', 'addFee', 'addWei', 'default']
    radio_fields = {'shipType': admin.HORIZONTAL}

    fieldsets = (
        ('基本信息', {'fields': ['name', 'shipType', 'iniWei', 'addFee']}),
        # ('指定区域', {'fields': ['on_prov']})
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(ShipAdmin, self).get_form(request, obj, change, **kwargs)
        query = District.objects.filter(pid=0)
        form.base_fields['prov'].queryset = query
        if obj:
            form.base_fields['prov'].initial = query.filter(id=obj.onProv).first()
        return form

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            itm = form.cleaned_data['prov']
            obj.onProv = itm.id if itm else 0
        super(ShipAdmin, self).save_model(request, obj, form, change)


@admin.register(Order)
class OrderAdmin(BaseAdmin):  # spu_title
    list_display = ['id', 'orderNo', 'created', 'totalFee', 'coupFee', 'realFee', 'shipFee', 'name', 'phone',
                    'address', 'shipNo', 'status', 'remark']

    search_fields = ['orderNo']
    list_filter = ['status']

    def get_queryset(self, request):
        return super(OrderAdmin, self).get_queryset(request)

    fieldsets = (
        ('订单信息', {'fields': ['orderNo']}),
        ('配送消息', {'fields': [('name', 'phone'), 'address', 'shipNo']})
    )


@admin.register(OrderSku)
class OrderAdmin(BaseAdmin):
    list_display = ['orderId', 'skuId', 'amount', 'shipFee', 'price', 'weight']
    search_fields = ['orderId']

    # def spu_title(self, obj):
    #     return Spu.objects.filter(id=Sku.objects.filter(id=obj.skuId).first().spuId).first().title
    #
    # spu_title.short_description = '商品名'


@admin.register(OrderSkuRefund)
class OrderRefundAdmin(BaseAdmin):
    list_display_links = None
    list_display = ['created', 'order_no', 'rc_name', 'rc_phone', 'refundFee', 'refundType', 'status']
    list_select_related = ['order']

    def order_no(self, obj):
        return obj.order_no

    order_no.short_description = '订单号'

    def rc_name(self, obj):
        return obj.order.name

    rc_name.short_description = '姓名'

    def rc_phone(self, obj):
        return obj.order.phone

    rc_phone.short_description = '电话号码'

    def get_queryset(self, request):
        return super(OrderRefundAdmin, self).get_queryset(request).annotate(
            order_no=RawSQL('''select o.orderNo from jkb_order_sku_refund osr
left join jkb_order_sku os on os.id=osr.orderSkuId
left join jkb_order o on o.id=os.orderId'''),
        )


@admin.register(PageConf)
class PageConfAdmin(BaseAdmin):

    def get_list_display(self, request):
        if request.user.is_superuser:
            return ['id', 'path', 'conf']
        return ['id', 'path', 'conf', 'appid']

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.appid = request.user.appid
        super(PageConfAdmin, self).save_model(request, obj, form, change)


@admin.register(HomeCate)
class HomeCateAdmin(BaseAdmin):
    form = HomeCateForm

    list_display = ('index', 'cate_name')

    def get_queryset(self, request):
        return super(HomeCateAdmin, self).get_queryset(request).annotate(cate_name=Subquery(
            Cate.objects.filter(id=OuterRef('cateId')).values('name')[:1]))

    def cate_name(self, obj):
        return obj.cate_name

    cate_name.short_description = '分类'

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        筛选数据
        """
        print(request.user.appid)
        form = super(HomeCateAdmin, self).get_form(request, obj, change, **kwargs)
        ids = HomeCate.objects.filter(appid=request.user.appid).values_list('cateId', flat=True)
        print("ids------", ids)
        query = Cate.objects.exclude(id__in=ids, pid=0).filter(appid=request.user.appid)
        print("queryyy-----", query[0:2])
        form.base_fields['cate'].queryset = query
        if obj:
            form.base_fields['cate'].initial = query.filter(id=obj.cateId).first()

        return form

    def save_model(self, request, obj, form, change):

        if form.is_valid():
            obj.cateId = form.cleaned_data['cate'].id
        else:
            obj.cateId = 0
        super(HomeCateAdmin, self).save_model(request, obj, form, change)


@admin.register(SpuCmt)
class SpuCmtAdmin(BaseAdmin):
    """
    商品评论
    """
    list_display = ['order_no', 'spu_title', 'content', 'replyTo', 'created']
    readonly_fields = ['userId', 'userType', 'spuId', 'orderId', 'content', 'replyTo']

    radio_fields = {'status': admin.HORIZONTAL}

    def get_queryset(self, request):
        return super(SpuCmtAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]),
            order_no=Subquery(Order.objects.filter(id=OuterRef('orderId')).values('orderNo')[:1])
        )

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品'

    def order_no(self, obj):
        return obj.order_no

    order_no.short_description = '订单号'


@admin.register(TagCmt)
class TagCmtAdmin(BaseAdmin):
    """
    评论标签
    """
    list_display = ['name', 'cnt']


@admin.register(CmtImg)
class CmtImgAdmin(BaseAdmin):
    """
    评论图片
    """
    list_display = ['cmtImg', 'cmtCont']

    def cmtImg(self, obj):
        return show_img(obj.image, w=64, h=64)

    cmtImg.short_description = '评论图片'

    def cmtCont(self, obj):
        return obj.cmt_cont

    cmtCont.short_description = '评论内容'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(CmtImgAdmin, self).get_queryset(request).annotate(
            cmt_cont=Subquery(SpuCmt.objects.filter(id=OuterRef('spuCmtId')).values('content')[:1]))


@admin.register(User)
class UserAdmin(BaseAdmin):
    """
    客户管理
    """
    # list_display = ['name', 'phone', 'addr', 'favor_count', 'order_count', 'total_spend']
    list_display = ['name', 'phone', 'full_addr', 'favor_count', 'order_count', 'total_spend']
    search_fields = ['name', 'phone']
    exclude = ['avatar']

    def full_addr(self, obj):
        return obj.full_addr

    full_addr.short_description = '地址'

    # 收藏数量
    def favor_count(self, obj):
        return obj.favor_count

    favor_count.short_description = '收藏数'

    # 订单数量
    def order_count(self, obj):
        return obj.order_count

    order_count.short_description = '订单数'

    # 消费金额
    def total_spend(self, obj):
        return obj.total_spend

    total_spend.short_description = '消费金额'

    def get_queryset(self, request):
        return super(UserAdmin, self).get_queryset(request).annotate(
            total_spend=Subquery(Order.objects.values('userId').filter(
                userId=OuterRef('pk'),
                status__in=(1, 2, 3)).annotate(total=Sum('realFee')).values('total')[:1], output_field=DecimalField()),
            favor_count=Subquery(Favor.objects.filter(userId=OuterRef('pk')).values('userId').annotate(
                fcnt=Count('userId')).values('fcnt')[:1], output_field=IntegerField()),
            order_count=Subquery(Order.objects.filter(userId=OuterRef('pk')).values('userId').annotate(
                ocnt=Count('userId')).values('ocnt')[:1], output_field=IntegerField()),
            full_addr=RawSQL('''select concat(p.name, c.name, e.name, a.detail) from jkb_addr a
left join jkb_district p on p.id=a.provId
left join jkb_district c on c.id=a.cityId
left join jkb_district e on e.id=a.areaId
where a.userId=jkb_user.id and a.userType=0 limit 1''', params=[])
        )


@admin.register(Activity)
class ActivityAdmin(BaseAdmin):
    """
    活动(秒杀管理)
    """
    list_display = ['title', 'beginTime', 'closeTime', 'state']


@admin.register(Staff)
class StaffAdmin(BaseAdmin):
    """
    员工
    """
    list_display = ['phone', 'name', 'role', 'created', 'state']


# 添加
@admin.register(SpuImg)
class SpuImgAdmin(BaseAdmin):
    """
    商品轮播图
    """
    list_display = ['spu_title', 'spuImg']
    search_fields = ['spu_title']
    form = SpuImgForm

    def spuImg(self, obj):
        return show_img(obj.image, w=64, h=64)

    spuImg.short_description = '商品轮播图'

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品名'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(SpuImgAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]))

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.spuId = form.cleaned_data['title'].id
        else:
            obj.spuId = 0
        super(SpuImgAdmin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(SpuImgAdmin, self).get_form(request, obj, change, **kwargs)
        query = Spu.objects.filter(appid=request.user.appid)
        form.base_fields['title'].queryset = query
        if obj:
            form.base_fields['title'].initial = Spu.objects.filter(id=obj.spuId).first()
        return form


@admin.register(SpuContent)
class SpuContentAdmin(BaseAdmin):
    """
    图文详情
    """
    list_display = ['spu_title', 'spuImg', 'video', 'text']
    search_fields = ['spu_title', 'text']
    form = SpuContentForm

    def spuImg(self, obj):
        return show_img(obj.image, w=64, h=64)

    spuImg.short_description = '商品详情图'

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品名'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(SpuContentAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]))

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.spuId = form.cleaned_data['title'].id
        else:
            obj.spuId = 0
        super(SpuContentAdmin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(SpuContentAdmin, self).get_form(request, obj, change, **kwargs)
        query = Spu.objects.filter(appid=request.user.appid)
        form.base_fields['title'].queryset = query
        if obj:
            form.base_fields['title'].initial = Spu.objects.filter(id=obj.spuId).first()
        return form


@admin.register(ShipProv)
class ShipProvAdmin(BaseAdmin):
    """
    指定省份运费规则
    """
    list_display = ['ship_name', 'prov_name', 'iniFee', 'iniWei', 'addFee', 'addWei']
    search_fields = ['ship_name', 'prov_name']
    form = ShipProvForm

    def ship_name(self, obj):
        return obj.ship_name

    ship_name.short_description = '运费规则'

    def prov_name(self, obj):
        return obj.prov_name

    prov_name.short_description = '省份名称'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(ShipProvAdmin, self).get_queryset(request).annotate(
            ship_name=Subquery(Ship.objects.filter(id=OuterRef('shipId')).values('name')[:1]),
            prov_name=Subquery(District.objects.filter(id=OuterRef('provId')).values('name')[:1]),
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        print(request.user.appid)
        form = super(ShipProvAdmin, self).get_form(request, obj, change, **kwargs)
        query1 = Ship.objects.filter(appid=request.user.appid)
        query2 = District.objects.filter(pid=0)
        form.base_fields['ship'].queryset = query1
        form.base_fields['prov'].queryset = query2
        if obj:
            form.base_fields['ship'].initial = Ship.objects.filter(id=obj.shipId).first()
            form.base_fields['prov'].initial = District.objects.filter(id=obj.provId).first()
        return form

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.shipId = form.cleaned_data['ship'].id
            obj.provId = form.cleaned_data['prov'].id
        else:
            obj.shipId = 0
            obj.provId = 0
        return super(ShipProvAdmin, self).save_model(request, obj, form, change)


@admin.register(SpuServ)
class SpuServAdmin(BaseAdmin):
    """
    保障服务
    """
    list_display = ['serv', 'spu_title']
    search_fields = ['spu_title']
    form = SpuServForm

    def spu_title(self, obj):
        return obj.spu_title

    spu_title.short_description = '商品名'

    def get_queryset(self, request):
        print(request.user.appid)
        return super(SpuServAdmin, self).get_queryset(request).annotate(
            spu_title=Subquery(Spu.objects.filter(id=OuterRef('spuId')).values('title')[:1]))

    def save_model(self, request, obj, form, change):
        if form.is_valid():
            obj.spuId = form.cleaned_data['title'].id
        else:
            obj.spuId = 0
        super(SpuServAdmin, self).save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(SpuServAdmin, self).get_form(request, obj, change, **kwargs)
        query = Spu.objects.filter(appid=request.user.appid)
        form.base_fields['title'].queryset = query
        if obj:
            form.base_fields['title'].initial = Spu.objects.filter(id=obj.spuId).first()
        return form
