from django.test import TestCase
from django.test import Client
from .models import *
from django.db.models import Count
import json
from test_extensions.django_common import DjangoCommon

from account.tests import RPC_LoginHelper
class RPC_MediaLibTest(DjangoCommon,RPC_LoginHelper):
    fixtures = ['medialib_test_fixture']
    
    def setUp(self):
        self.login_helper_setUp()
    def test_mediaLibraryList(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/library/"
        params = {}
        response = logged_client.get(url, params)
        data = json.loads(response.content)
        returned = data['data'][0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(returned["owner"] , 2)
        self.assertEqual(returned["acl_is_default"] , True)
        self.assertEqual(returned["name"] , "User Media Library")
    
    
    def test_mediaLibraryGetItems(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/library/6/items"  #library id is 6 to match data on the test fixture
        params = {}
        response = logged_client.get(url, params)
        # return the items from a specific media library
        self.assertEqual(response.status_code, 200) # no crash

        data = json.loads(response.content)
        returned = data['data'][0]
        self.assertEqual(returned["kind"] , "I")
        self.assertEqual(returned["description"] , "test")
        self.assertEqual(returned["render_error"] , "")
        self.assertEqual(returned["name"] , "test")

            
    def test_mediaLibraryGet(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/library/6"
        params = {}
        response = logged_client.get(url, params)
        self.assertEqual(response.status_code, 200) # no crash
        self.assert_response_contains('User Media Library',response)
        #Now test for invalid object.
        url = "/medialib/library/100"
        params = {}
        response = logged_client.get(url, params)
        self.assertEqual(response.status_code, 404) # no crash

    def NOtest_mediaLibrarySet(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/library/6"
        params = {'description':'changed description'}
        response = logged_client.post(url, params)
        self.assertEqual(response.status_code, 200) # no crash
        # verify description field is changed
        desc = MediaLibrary.objects.get(pk=6).description
        self.assertEqual(desc,'changed description')


    def NOtest_mediaItemSet(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/item/2" # item is 2 to fit fixture
        params = {'description':'changed description'}
        response = logged_client.post(url, params)
        self.assertEqual(response.status_code, 200) # no crash
        # verify description field is changed
        desc = MediaItem.objects.get(pk=2).description
        self.assertEqual(desc,'changed description')


    def NOtest_mediaItemNew(self):
        #create a fake .gif image file for testing
        import base64
        import io
        gif64 = "R0lGODdhAQABAIABAGtdWv///ywAAAAAAQABAAACAkQBADs="
        mygif =  base64.b64decode(gif64)
        fake_file = io.StringIO(mygif)
        fake_file.name = 'noimage.gif'
        #now upload the gif using the API
        libcount= MediaItem.objects.all().count()
        logged_client = self.default_client_login_helper()
        url = "/medialib/library/6/new"
        params = {'name':'noimage.gif','file':fake_file}
        response = logged_client.post(url, params)
        self.assertEqual(response.status_code, 200) # no crash
        data = json.loads(response.content)
        self.assertEqual(data['status'],True)
        self.assertEqual(libcount+1,MediaItem.objects.all().count())
    
    def test_mediaItemGet(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/item/2"
        params = {}
        response = logged_client.get(url, params)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200) # no crash
        expected  = {"kind": "I",
                     "description": "test",
                     "created": 1314740695.0,
                     "library": 6,
                     "render_error": "",
                     "state": 200,
                     "id": 2,
                     "name": "test"}
        self.assertEqual(response.status_code, 200) # no crash
        for key,value in list(expected.items()) :
            self.assertEqual(data[key], value,key)  # data matches fixture


    def test_mediaItemGet_Token(self):
        VALID_TOKEN = '2.gv.cdc4ec2fa3e4a05a1e65' #2. is the item id
        logged_client = self.default_client_login_helper()
        url = "/medialib/item/"+VALID_TOKEN+"/renditions"
        params = {}
        response = logged_client.get(url, params)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200) # no crash
        expected  = {'use': 'video',
                     'name': '360p',
                     'created': 1314813828.0,
                     'bytes': 719486,
                     'height': 360,
                     'width': 640,
                     'id': 1
                     }
        self.assertEqual(response.status_code, 200) # no crash
        for key,value in list(expected.items()) :
            self.assertEqual(data['data'][0][key], value,key)  # data matches fixture

    
    def NOtest_mediaItemDelete(self):
        logged_client = self.default_client_login_helper()
        url = "/medialib/item/2"
        params = {}
        self.assertEqual(1,MediaItem.objects.filter(pk=2).count()) #verify item is there
        response = logged_client.delete(url, params)
        self.assertEqual(response.status_code, 200) # no crash
        self.assertEqual(0,MediaItem.objects.filter(pk=2).count()) #test item is NOT there
