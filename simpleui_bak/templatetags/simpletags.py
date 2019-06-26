# -*- coding: utf-8 -*-

import django
from django import template
from django.utils.html import format_html
from django.conf import settings
from django.utils.safestring import mark_safe
from collections import OrderedDict

from django.templatetags import static

import os
import json

import platform
import socket

import simpleui

import base64
import time

from django.db import models

register = template.Library()


@register.filter
def get_icon(name):
    # 默认为文件图标
    cls = ""

    return format_html('<i class="icon {}"></i>', cls)


@register.simple_tag(takes_context=True)
def context_test(context):
    print(context)
    pass


# context.get('cl').filter_specs[1].links
@register.simple_tag(takes_context=True)
def load_dates(context):
    data = {}
    cl = context.get('cl')
    if cl.has_filters:
        for spec in cl.filter_specs:
            field = spec.field
            field_type = None
            if isinstance(field, models.DateTimeField):
                field_type = 'datetime'
            elif isinstance(field, models.DateField):
                field_type = 'date'
            elif isinstance(field, models.TimeField):
                field_type = 'time'

            if field_type:
                data[field.name] = field_type
    context['date_field'] = data

    return '<script type="text/javascript">var searchDates={}</script>'.format(json.dumps(data))


@register.filter
def get_date_type(spec):
    field = spec.field
    field_type = ''
    if isinstance(field, models.DateTimeField):
        field_type = 'datetime'
    elif isinstance(field, models.DateField):
        field_type = 'date'
    elif isinstance(field, models.TimeField):
        field_type = 'time'

    return field_type


@register.filter
def test(obj):
    print(obj)
    # pass
    return ''


@register.filter
def to_str(obj):
    return str(obj)


@register.filter
def date_to_json(obj):
    return json.dumps(obj.date_params)


@register.simple_tag(takes_context=True)
def home_page(context):
    """
    处理首页，通过设置判断打开的是默认页还是自定义的页面
    :return:
    :param context:
    :return:
    """

    context['title'] = '首页'
    context['icon'] = 'el-icon-menu'

    return ''


def __get_config(name):
    value = os.environ.get(name, getattr(settings, name, None))
    return value


@register.filter
def get_config(key):
    return __get_config(key)


@register.simple_tag
def get_server_info():
    dict = {
        'Network': platform.node(),
        'OS': platform.platform(),
    }
    return format_table(dict)


@register.simple_tag
def get_app_info():
    return format_table({
        'Python': platform.python_version(),
        'Django': django.get_version(),
        'Simpleui': simpleui.get_version()
    })


def format_table(dict):
    html = '<table class="simpleui-table"><tbody>'
    for key in dict:
        html += '<tr><th>{}</th><td>{}</td></tr>'.format(key, dict.get(key))
    html += '</tbody></table>'
    return format_html(html)


@register.simple_tag(takes_context=True)
def menus(context):
    data = []

    # return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    config = get_config('SIMPLEUI_CONFIG')

    app_list = context.get('app_list')
    for app in app_list:
        models = []
        if app.get('models'):
            for m in app.get('models'):
                models.append({
                    'name': str(m.get('name')),
                    'icon': get_icon(m.get('object_name')),
                    'url': m.get('admin_url'),
                    'addUrl': m.get('add_url'),
                    'breadcrumbs': [str(app.get('name')), str(m.get('name'))]
                })

        module = {
            'name': str(app.get('name')),
            'icon': get_icon(app.get('app_label')),
            'models': models
        }
        data.append(module)

    # 如果有menu 就读取，没有就调用系统的
    if config and 'menus' in config:
        if 'system_keep' in config:
            temp = config.get('menus')
            for i in temp:
                data.append(i)
        else:
            data = config.get('menus')

    data = []

    return '<script type="text/javascript">var menus={}</script>'.format(json.dumps(data))


def get_icon(obj):
    dict = {
        'auth': 'fas fa-shield-alt',
        'User': 'far fa-user',
        'Group': 'fas fa-users-cog'

    }
    temp = dict.get(obj)
    if not temp:
        return 'far fa-file'
    return temp


@register.simple_tag(takes_context=True)
def load_message(context):
    messages = context.get('messages')
    array = []
    if messages:
        for msg in messages:
            array.append({
                'msg': msg.message,
                'tag': msg.tags
            })

    return '<script type="text/javascript"> var messages={}</script>'.format(array)


@register.simple_tag(takes_context=True)
def context_to_json(context):
    json_str = '{}'

    return mark_safe(json_str)


@register.simple_tag()
def get_language():
    return django.utils.translation.get_language()


@register.filter
def get_language_code(val):
    return django.utils.translation.get_language()


def get_analysis_config():
    val = __get_config('SIMPLEUI_ANALYSIS')
    if not val and val == False:
        return False
    return True


@register.simple_tag(takes_context=True)
def ordered_menu(context):
    modmap = {}
    for app in context['app_list']:
        label = app['app_label']
        for m in app['models']:
            modmap['.'.join([label, m['object_name']])] = m

    def gen_menu(key, itms):

        print(key, '-----', itms)

        children = []
        for itm in itms:
            if isinstance(itm, tuple):
                subkey, subitems = itm
                children.append(gen_menu(subkey, subitems))
            else:
                model = modmap.get(itm)
                if model:
                    children.append(format_html('<dd><a lay-href="{}"></a></dd>', model['admin_url']))

        return format_html('''<li class="class="layui-nav-item layui-nav-itemed"">
        <a href="javascript:;">{}</a>
        <dl class="layui-nav-child">{}</dl></li>''', key, ''.join(children))

    return format_html('''<div class="layui-side layui-side-menu"><div class="layui-side-scroll">{}</div></div>''',
                       ''.join([gen_menu(key, itms) for key, itms in settings.SIDE_MENU]))



