from django.db import models
from django.conf import settings

from account.models import Member

from rest.views import *
from rest.decorators import *
from rest import search
from rest import helpers
from rest import crypto

from objict import objict

from pushit.models import Product, Release

import json

import base64

from datetime import datetime, timedelta
import time

@urlPOST (r'^product$')
@urlPOST (r'^product/(?P<product_id>\d+)$')
@urlPOST (r'^product/uuid/(?P<uuid>\w+)$')
@login_optional
def updateProduct(request, product_id=None, uuid=None):
    if not request.member:
        return restPermissionDenied(request)
    product = None
    if not product_id and not uuid:
        product = Product.createFromRequest(request, owner=request.member, group=request.group)
    elif product_id:
        product = Product.objects.filter(pk=product_id).last()
    elif uuid:
        product = Product.objects.filter(oid=uuid).last()

    if not product:
        return restStatus(request, False, error="unknown product")
    if product.owner != request.member or (product.group and not request.member.isMemberOf(product.group)):
        if not request.user.is_staff:
            return restPermissionDenied(request)
        product.saveFromRequest(request, owner=request.member)
    return restGet(request, product, **Product.getGraph("default"))

@urlGET (r'^product/(?P<product_id>\d+)$')
@urlGET (r'^product/uuid/(?P<uuid>\w+)$')
@login_optional
def getProduct(request, product_id=None, uuid=None):
    product = None
    if product_id:
        product = Product.objects.filter(pk=product_id).last()
    elif uuid:
        product = Product.objects.filter(oid=uuid).last()
    else:
        return restNotFound(request)

    if not product:
        return restStatus(request, False, error="unknown product")
    if not product.is_public and not request.member:
        return restPermissionDenied(request, "not logged in")
    return product.restGet(request)

@urlGET (r'^product$')
@login_optional
def listProducts(request):
    if not request.member:
        return restPermissionDenied(request)
    if not request.member.is_staff:
        return restPermissionDenied(request)

    kind = request.DATA.get("kind")
    qset = Product.objects.filter(archived=False)
    if kind:
        qset = qset.filter(kind=kind)

    return restList(request, qset, **Product.getGraph("default"))

@urlPOST (r'^release$')
@urlPOST (r'^release/(?P<release_id>\d+)$')
@login_optional
def updateRelease(request, release_id=None):
    if not request.member:
        return restPermissionDenied(request)

    if not release_id:
        auto_version = request.DATA.get("auto_version", False)
        prod_uuid = request.DATA.get(["product", "product_uuid"])
        product = None
        if prod_uuid:
            product = Product.objects.filter(oid=prod_uuid).last()
        else:
            prod_id = request.DATA.get("product_id")
            if prod_id:
                product = Product.objects.filter(pk=prod_id).last()
        if not product:
            return restStatus(request, False, error="product required")
        version_num = request.DATA.get("version_num", field_type=int)
        last_release = Release.objects.filter(product=product).order_by("-version_num").first()

        if not version_num:
            if last_release and auto_version:
                version_num = last_release.version_num + 1
            elif auto_version:
                version_num = 1
            else:
                return restStatus(request, False, error="no version info supplied, try auto_version=1")
        elif last_release and version_num <= last_release.version_num:
            return restStatus(request, False, error="version is not greater then last")

        release = Release.createFromRequest(request, product=product, owner=request.member, group=request.group, version_num=version_num)
    else:
        release = Release.objects.filter(pk=release_id).last()
        if not release:
            return restStatus(request, False, error="unknown release")
        if release.owner != request.member or (release.product.group and not request.member.isMemberOf(release.product.group)):
            if not request.user.is_staff:
                return restPermissionDenied(request)
        release.saveFromRequest(request, owner=request.member)
    if request.DATA.get("make_current"):
        release.makeCurrent()
    elif request.DATA.get("make_beta"):
        release.makeCurrent()
    return restGet(request, release, **Release.getGraph("default"))

@urlGET (r'^release/(?P<release_id>\d+)$')
@login_optional
def getRelease(request, release_id):
    release = Release.objects.filter(pk=release_id).last()
    if not release:
        return restStatus(request, False, error="unknown release")
    if not release.product.is_public and not request.member:
        return restPermissionDenied(request, "not logged in")
    return restGet(request, release, **Release.getGraph("default"))

def reportRestIssue(subject, message, perm="rest_errors", email_only=False):
    # notifyWithPermission(perm, subject, message=None, template=None, context=None, email_only=False)
    # notify email only
    Member.notifyWithPermission(perm, subject, message, email_only=email_only)

from random import randint
@rest_async
def update_code(git_updater, updater_md5=None, branch=None):
    # randomize the hit so we avoid collisions (gitlabs issues)
    time.sleep(randint(1, 10))
    import os
    import subprocess
    # check md5sum
    if updater_md5:
        cur_md5 = crypto.getFileMD5(git_updater)
        if cur_md5.lower() != updater_md5.lower():
            reportRestIssue("md5 check failed", "{}\ncould not be executed, md5 check failed".format(git_updater))
            return

    # TODO
    # - check for errors and permissions
    cmd = ["sudo", "-lU", "ec2-user", git_updater, branch]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    if err.strip():
        helpers.log_print("WARNING: cannot run {}, we don't have sudo rights".format(git_updater))
        helpers.log_print("WARNING: add {} to your sudo user".format(git_updater))
        return
    # - lock it so we kill any updates in progress and start a new one
    cmd = ["sudo", "-u", "ec2-user", git_updater, branch]
    helpers.log_print("updating...", cmd)
    subprocess.Popen(cmd, close_fds=True)

@rest_async
def new_release(product, tag, url, msg):
    version_str = tag
    if tag.startswith("v"):
        version_str = tag[1:]

    rev = tag.split('.')[-1]
    if not rev.isdigit():
        return False
    token =  product.getProperty("git_token", "XXXXX")
    release = Release(product=product, version_num=int(rev), version_str=version_str, notes=msg)
    release.owner = product.owner
    release_url = "{}/repository/{}/archive.zip?private_token={}".format(url, tag, token)
    release.save()
    helpers.log_print(release_url)
    release.set_media(release_url, True)
    release.makeCurrent()

def on_git_merge_request(info, request):
    state = request.DATA.get("object_attributes.state")
    target_branch = request.DATA.get("object_attributes.target_branch")

    git_branch = info.get("branch")
    git_updater = info.get("updater")
    git_updater_md5 = info.get("updater_md5", None)

    if target_branch == git_branch:
        reportRestIssue(
            "{} update({}) on: {}".format(info.get("project", "n/a"), getattr(settings, "SERVER_NAME", "unknown"), git_branch),
            "<pre>{}</pre>".format(helpers.dictToString(request.DATA.asDict(), True)),
            "git_updates", email_only=True)
        update_code(git_updater, git_updater_md5, git_branch)

def on_git_push_request(info, hook_request):
    git_branch = info.get("branch")
    git_updater = info.get("updater")
    git_updater_md5 = info.get("updater_md5", None)
    update_code(git_updater, git_updater_md5, git_branch)

def on_git_new_release(info, request):
    project = request.DATA.get("project.name")
    helpers.log_print("NEW RELEASE FOR {}".format(project))
    product = Product.objects.filter(name=project).last()
    if not product:
        helpers.log_print("PRODUCT NOT FOUND")
        return
    tag = request.DATA.get("ref").split('/')[-1]
    msg = request.DATA.get("message")
    url = request.DATA.get("project.web_url")
    if product and msg:
        new_release(product, tag, url, msg)


def parseGitLab(request):
    info = objict(vendor="gitlab")
    info.name = request.DATA.get("project.name")
    info.kind = request.DATA.get("object_kind")
    if "ref" in request.DATA:
        info.branch = request.DATA.get("ref").split('/')[-1]
    if info.kind == "merge_request":
        info.state = request.DATA.get("object_attributes.state", None)
        if info.state == "merged":
            info.kind = "merged"
    return info


def parseGithub(request):
    info = objict(vendor="github")
    info.name = request.DATA.get("repository.name")
    info.kind = request.DATA.getHeader("HTTP_X_GITHUB_EVENT")
    if "ref" in request.DATA:
        info.branch = request.DATA.get("ref").split('/')[-1]
    return info


def getProjectForBranch(proj_info, branch):
    if proj_info is None:
        return None
    if type(proj_info) is list:
        for pi in proj_info:
            if pi["branch"] == branch:
                return pi
        return None
    if project_info["branch"] == branch:
        return proj_info
    return None


@urlPOST (r'^hooks/git_update$')
def on_git_hook(request):
    request.DATA.log()
    sec_key = request.DATA.get("token")
    git_key = getattr(settings, "GIT_KEY", "hookswhat")
    is_gitlab = True
    hook_request = None
    req_key = request.DATA.getHeader("HTTP_X_GITLAB_TOKEN")
    if req_key is not None:
        hook_request = parseGitLab(request)
    else:
        req_key = request.DATA.getHeader("HTTP_X_HUB_SIGNATURE_256")
        if req_key is not None:
            is_gitlab = False
            hook_request = parseGithub(request)    

    if sec_key != git_key:
        if req_key is None:
            helpers.log_print("NO TOKEN")
            helpers.log_print(request.META)
            return restPermissionDenied(request)

    git_projects = getattr(settings, "GIT_PROJECTS", None)

    if hook_request.name not in git_projects:
        return restStatus(request, False, error="no config for project")

    proj_info = getProjectForBranch(git_projects.get(hook_request.name), hook_request.branch)
    if proj_info is None:
        return restStatus(request, False, error="no branch for project")

    if hook_request.kind == "push":
        on_git_push_request(proj_info, hook_request)

    # kind = request.DATA.get("object_kind")
    # project = request.DATA.get("project.name")

    # git_projects = getattr(settings, "GIT_PROJECTS", None)
    # if git_projects and project in git_projects:
    #     proj_info = git_projects.get(project)
    #     # now lets handle different kinds
    #     if kind == "merge_request":
    #         # now check the state
    #         state = request.DATA.get("object_attributes.state", None)
    #         if state != "merged":
    #             return restStatus(request, True)
    #         if type(proj_info) is list:
    #             for info in proj_info:
    #                 info["project"] = project
    #                 on_git_merge_request(info, request)
    #         else:
    #             on_git_merge_request(proj_info, request)
    #     elif kind == "push":
    #         if type(proj_info) is list:
    #             for info in proj_info:
    #                 info["project"] = project
    #                 on_git_push_request(info, request)
    #         else:
    #             proj_info["project"] = project
    #             on_git_push_request(proj_info, request)
    #     elif kind == "tag_push":
    #         on_git_new_release(proj_info, request)
    # elif kind == "tag_push":
    #     proj_info = git_projects.get(project)
    #     on_git_new_release(proj_info, request)
    # else:
    #     helpers.log_print("No Config for Project {}".format(project))
    return restStatus(request, True)

