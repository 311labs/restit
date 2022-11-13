from rest import decorators as rd
from rest import crypto
from rest.mail import render_to_mail
from rest.views import restStatus, restGet, restPermissionDenied
from rest.jwtoken import JWToken, JWT_KEY
from rest import helpers
from account import models as am
from medialib.qrcode import generateQRCode
from django.http import HttpResponse
from datetime import datetime, timedelta


@rd.urlPOST(r'^login$')
@rd.urlPOST(r'^login/$')
@rd.never_cache
def member_login(request):
    username = request.DATA.get('username', None)
    auth_code = request.DATA.get(["auth_code", "code"], None)
    if username and auth_code:
        return member_login_uname_code(request, username, auth_code)
    password = request.DATA.get('password', None)
    if username and password:
        return member_login_uname_pword(request, username, password)
    return restStatus(request, False, error="Invalid credentials", error_code=401)


@rd.urlPOST(r'^jwt/login$')
@rd.urlPOST(r'^jwt/login/$')
@rd.never_cache
def jwt_login(request):
    # poor mans JWT, carried over
    username = request.DATA.get('username', None)
    if not username:
        return restStatus(request, False, error="Password and/or Username is incorrect", error_code=422)
    member = getMemberByUsername(username)
    if not member:
        return restStatus(request, False, error="Password and/or Username is incorrect", error_code=422)
    password = request.DATA.get('password', None)
    member.canLogin(request)  # throws exception if cannot login
    if not member.login(request=request, password=password, use_jwt=True):
        member.log("login_failed", "incorrect password", request, method="login", level=31)
        return restStatus(request, False, error="Password or Username is incorrect", error_code=401)
    if member.security_token is None or member.security_token == JWT_KEY:
        member.refreshSecurityToken()
    member.log("jwt_login", "jwt login succesful", request, method="login", level=7)
    
    device_id = request.DATA.get(["device_id", "deviceID"])
    token = JWToken(user_id=member.pk, key=member.security_token, device_id=device_id)

    request.user = member.getUser()
    request.member = member
    request.signature = token.session_id
    request.auth_session = am.AuthSession.NewSession(request)
    if bool(device_id):
        am.MemberDevice.register(request, member, device_id)
    
    request.jwt_token = token.access_token  # this tells the middleware to store in cookie
    return restGet(request, dict(access=token.access_token, refresh=token.refresh_token, id=member.pk))


@rd.urlPOST(r'^jwt/logout$')
@rd.urlPOST(r'^jwt/logout/$')
@rd.never_cache
def jwt_logout(request):
    # this will force our token to change
    if request.member:
        request.member.log("jwt_logout", "jwt logout", request, method="logout", level=25)
        request.member.sendEvent("logout", "user requested logout")
        request.member.refreshSecurityToken()
        request.clear_jwt_cookie = True  # tells middleware to remove from cookie
    return restStatus(request, True)


@rd.urlPOST(r'^jwt/refresh$')
@rd.urlPOST(r'^jwt/refresh/$')
@rd.never_cache
def jwt_refresh(request):
    # poor mans JWT, carried over
    rtoken = request.DATA.get(['refresh_token', 'refresh'], None)
    if rtoken is None:
        return restStatus(request, False)
    token = JWToken(token=rtoken)
    member = am.Member.objects.filter(pk=token.payload.user_id).last()
    if not member:
        return restStatus(request, False, error="Password or Username is incorrect", error_code=422)
    if member.security_token is None:
        member.refreshSecurityToken()
    token.key = member.security_token
    if not token.is_valid or token.payload.user_id is None:
        return restStatus(request, False, error="invalid token", error_code=-702)
    member.canLogin()
    token.refresh()
    request.jwt_token = token.access_token  # this tells the middleware to store in cookie
    return restGet(request, dict(access=token.access_token, refresh=token.refresh_token))


def getMemberByUsername(username):
    member = None
    username = username.lower()
    if username.count('@') == 1:
        member = am.Member.objects.filter(email=username).last()
    if not member:
        member = am.Member.objects.filter(username=username).last()
    return member


def member_login_uname_pword(request, username, password):
    member = getMemberByUsername(username)
    if not member:
        return restStatus(request, False, error="Password or Username is not correct", error_code=422)
    member.canLogin(request)  # throws exception if cannot login
    if member.requires_topt:
        totp_code = request.DATA.get("totp_code", None)
        if totp_code is None:
            member.log("login_blocked", "requires MFA (TOTP)", request, method="login", level=31)
            return restStatus(request, False, error="requires MFA (TOTP)", error_code=455)
        if not member.totp_verify(totp_code):
            member.log("login_blocked", "invalid MFA code", request, method="login", level=31)
            return restStatus(request, False, error="invalid MFA code", error_code=456)
    if not member.login(request=request, password=password, use_jwt=False):
        member.log("login_failed", "incorrect password", request, method="login", level=31)
        return restStatus(request, False, error="Password or Username is incorrect", error_code=401)

    member.log("password_login", "password login", request, method="login", level=7)
    return member.restGet(request, graph="me")


def member_login_uname_code(request, username, auth_code):
    member = getMemberByUsername(username)
    if not member:
        return restStatus(request, False, error="Username or code is incorrect", error_code=422)
    if not member.is_active:
        member.log("login_blocked", "account is not active", request, method="login", level=31)
        return restStatus(request, False, error="Account disabled", error_code=410)
    if member.is_blocked:
        member.log("login_blocked", "account is locked out", request, method="login", level=31)
        return restStatus(request, False, error="Account locked out", error_code=411)
    auth_code = auth_code.replace('-', '').replace(' ', '')
    if member.auth_code != auth_code:
        return restPermissionDenied(request, "token most likely expired, try again", error_code=492)
    if member.auth_code_expires < datetime.now():
        return restPermissionDenied(request, "token expired", error_code=493)
    password = request.DATA.get(['password', 'new_password'], None)
    if password:
        member.setPassword(password)
    member.auth_code = None
    member.auth_code_expires = None
    member.save()
    member.log("code_login", "code login", request, method="login", level=8)
    # we still force the user to use JWT after code login
    if member.security_token is None:
        member.refreshSecurityToken()
    token = JWToken(user_id=member.pk, key=member.security_token)
    return restGet(request, dict(access=token.access_token, refresh=token.refresh_token, id=member.pk))



@rd.url(r'^logout$')
@rd.url(r'^logout/$')
@rd.never_cache
def member_logout(request):
    """
    | Parameters: none

    | Return: status + error

    | Logout
    """
    if request.user.is_authenticated:
        request.user.log("logout", "user logged out", request, method="logout", level=8)
    request.member.logout(request)
    return restStatus(request, True)


@rd.url(r'^loggedin/$')
@rd.never_cache
def is_member_logged_in(request):
    """
    | param: none

    | Return: status + error

    | Check if the current user is logged in
    """
    if request.user:
        return restStatus(request, request.user.is_authenticated)
    return restStatus(request, False)


@rd.urlPOST (r'^forgot$')
@rd.urlPOST (r'^forget/$')
@rd.never_cache
def member_forgot_password(request):
    """
    | param: username = use the username as the lookup
    | param: email = use the email as the lookup

    | Return: status + error

    | Send fgroupet password reset instructions
    """
    username = request.DATA.get('username', None)
    if not username:
        return restStatus(request, False, error="Username is required")
    member = getMemberByUsername(username)
    if not member:
        return restStatus(request, False, error="Password or Username is incorrect", error_code=422)
    if not member.is_active:
        member.log("login_blocked", "account is not active", request, method="login", level=31)
        return restStatus(request, False, error="Account disabled", error_code=410)
    if member.is_blocked:
        member.log("login_blocked", "account is locked out", request, method="login", level=31)
        return restStatus(request, False, error="Account locked out", error_code=411)

    if request.DATA.get("use_code", False):
        return member_forgot_password_code(request, member)

    member.auth_code = crypto.randomString(16)
    member.save()
    member.log("forgot", "user requested password reset", request, method="password_reset", level=17)

    token = "{}-{}".format(crypto.obfuscateID("Member", member.id), member.auth_code)
    render_to_mail("registration/password_reset_email", {
        'user': member,
        'uuid': member.uuid,
        'token': token,
        'subject': 'password reset',
        'to': [member.email],
    })

    return restStatus(request, True, msg="Password reset instructions have been sent to your email.")


def member_forgot_password_code(request, member):
    member.generateAuthCode(6)
    code = "{} {}".format(member.auth_code[:3], member.auth_code[3:])

    context = helpers.getContext(
        request,
        user=member,
        code=code)

    if member.notify(
            context=context,
            email_only=False,
            force=True,
            subject="Login Code",
            template="email/reset_code.html",
            sms_msg="Your login code is:\n{}".format(code)):
        member.log("requested", "user requested password reset code", request, method="login_token", level=8)
        return restStatus(request, True)
    member.log("error", "No valid email/phone, check users profile!", request, method="login_token", level=6)
    return restStatus(request, False, error="No valid email/phone, check users profile!")


# time based one time passwords
@rd.urlGET(r'^totp/qrcode$')
@rd.login_required
def totp_qrcode(request):
    token = request.member.getProperty("totp_token", category="secrets", default=None)
    reset = request.DATA.get("force_reset", False)
    if token is not None and not reset:
        return restPermissionDenied(request, "token exists")
    params = dict(data=request.member.totp_getURI())
    error = request.DATA.get("error", None)
    if error is not None:
        params["error"] = error
    version = request.DATA.get("version", None)
    if version is not None:
        params["version"] = int(version)
    img_format = request.DATA.get("format", "png")
    if img_format is not None:
        params["img_format"] = img_format
    scale = request.DATA.get("scale", 4)
    if scale is not None:
        params["scale"] = int(scale)
    code = generateQRCode(**params)
    if img_format == "base64":
        return HttpResponse(code, content_type="text/plain")
    elif img_format == "svg":
        return HttpResponse(code, content_type="image/svg+xml")
    return HttpResponse(code, content_type="image/png")


# time based one time passwords
@rd.urlPOST(r'^totp/verify$')
@rd.login_required
def totp_verify(request):
    code = request.DATA.get("code", None)
    if code is None or len(code) != 6:
        return restPermissionDenied(request, "invalid code format")
    if not request.member.totp_verify(code):
        return restPermissionDenied(request, "invalid code")
    return restStatus(request, True)


