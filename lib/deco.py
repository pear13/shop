# 装饰器定义模块

from functools import wraps
import jwt
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from lib import gen_resp, Code, RespData
from main.models import User

log = logging.getLogger()


def check_login(func):
    """
    每个接口必须引入
    :param func:
    :return:
    """

    @csrf_exempt  # 仅接口去csrf, 如果可以应该去掉所有的中间件
    @wraps(func)
    def wrapper(request, *args):

        start = timezone.now()

        token = request.headers.get('jkbtoken')
        if not token:
            return gen_resp(Code.ILLEGAL)
        try:
            data = jwt.decode(token, verify=False)
            user: User = User.objects.filter(openid=data.get('openid'), appid=data.get('appid')).first()
            if user is None:
                return gen_resp(msg='用户不存在')
            jwt.decode(token, user.apikey, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return gen_resp(msg='token已经过期')
        except Exception as e:
            log.warning(f'token异常：{e}')
            return gen_resp(msg='token异常')
        request.user = user  # 注意这里的user有别于管理后台的user, 管理后台request.user对应Merc表

        before = ['='*40, request.get_raw_uri()]
        if request.content_type in ['application/xml', 'application/json']:
            before.append('body>\n' + request.body.decode())
        elif request.content_type == 'application/x-www-form-urlencoded':
            before.append('form>\n' + str(request.POST.dict()))
        log.info('\n'.join(before))

        try:
            response = func(request, *args)
            if response['Content-Type'] in ['application/json']:
                log.info('\n'.join(['resp>\n' + response.content.decode(),
                                    '=' * 40 + ' cost time:' + str(timezone.now() - start)]))
            return response
        except RespData:
            return gen_resp(**RespData.data)
        except Exception as err:
            log.error(err)
            return gen_resp(Code.UNKNOWN)

    return wrapper


def after_order(func):

    @wraps(func)
    def wrapper(*args):
        rsp = func(*args)
        return rsp
    return wrapper


def after_payed(func):

    @wraps(func)
    def wrapper(*args):
        rsp = func(*args)
        return rsp
    return wrapper



