# RESTIT.. a REST framework for DJANGO

### Quick Starnes

1. 

## Quick Overview

This framework makes it easy to build a rest framework to use with any web or applicaiton development.

You can take any model and turn them into a REST Model by inheriting from RestModel.

```python
class ExampleTODO(models.Model, RestModel):
	your standard django fields
  ...
```



Next in your DJANGO app create a "rpc.py" file.

```python
# decorator that defines your routes, note the app_name is assumed
@url(r'^todo$')
@url(r'^todo/(?P<pk>\d+)$')
@login_required
def on_rest_todo(request, pk=None):
	return ExampleTODO.on_rest_request(request, pk)
```

This will give you a full rest interface into your Django model.



### But wait there's more...

This framework is pretty powerful and allow you to define how you want to return your model objects, and how deep!

```python
class ExampleTODO(models.Model, RestModel):
	class RestMeta:
		GRAPHS = {
			"default": {
        "exclude":["priority"],
				"graphs":{
					"user":"default"
				}
			},
			"list": {
        "fields":["id", "name", "priority"]
			}
		}
	user = models.ForeignKey(User, related_name="+")
  name = models.CharField(max_length=80)
  description = models.TextField(max_length=80)
  priority = models.IntegerField(default=0)
```

Above you can we we can define "graphs" that let us control what is returned.

So if we go to http://localhost:8000/rpc/rest_example/todo it will default to the "list" graph and return something that looks like...

```json
{
	"status": true,
	"size": 25,
	"count": 2,
	"data": [
		{
			"id": 1,
			"name": "test 1",
			"priority": 1,
      "user": 21
		},
		{
			"id": 2,
			"name": "test 2",
			"priority": 1,
      "user": 21
		},
	]
}
```



So if we go to http://localhost:8000/rpc/rest_example/todo?graph=default

```json
{
	"status": true,
	"size": 25,
	"count": 2,
	"data": [
		{
			"id": 1,
			"name": "test 1",
			"description": "this is test 1",
      "user": {
        "id": 21,
        "username": "jsmith",
        "display_name": "TEST USER 5",
        "avatar": "http://localhost:8000/media/ax1fg.png"
      }
		},
		{
			"id": 2,
			"name": "test 2",
			"description": "this is test 2",
      "user": {
        "id": 21,
        "username": "jsmith",
        "display_name": "TEST USER 5",
        "avatar": "http://localhost:8000/media/ax1fg.png"
      }
		},
	]
}
```





## More details...

## RestModel

The RestModel Class is a helper class that helps existing models adapt to the REST framework.  It is not required but highly recommended.

### API helpers

Key methods you can override

```
	def on_rest_get(self, request):
		# override the get method
		return self.restGet(request, graph)

	def on_rest_post(self, request):
		# override the post method
		return self.restGet(request, graph) 
	
	def on_rest_pre_save(self, request):
		# called before instance saved via rest, no return
		pass
		
	def on_rest_created(self, request):
		# called after new instance created via rest, no return
		pass

	def on_rest_saved(self, request, is_new=False):
		# called after old instance saved via rest, no return
		pass

	def on_rest_delete(self, request):
		can_delete = getattr(self.RestMeta, "CAN_DELETE", False)
		if not can_delete:
			return self.restStatus(request, False, error="deletion not allowed via rest for this model.")
		self.delete()
		return GRAPH_HELPERS.restStatus(request, True)

	@classmethod
	def onRestCanSave(cls, request):
		# override to validate permissions or anything if this can create or save this instance
		return True
		
	@classmethod
	def on_rest_list_filter(cls, request, qset):
		# override on do any pre filters, returns new qset
		# qset = qset.filter(id__gt=50)
		return qset
		
	@classmethod
	def on_rest_list(cls, request, qset=None):
		# normally you would override on_rest_list_filter, but you could override this
		return cls.restList(request, qset)
	
	@classmethod
	def on_rest_create(cls, request, pk=None):
		obj = cls.createFromRequest(request)
		return obj.restGet(request)
```



#### Creating and Saving

`createFromRequest(request, **kwargs)` - this allows you to pass a request object (normally a post) and create a new model from that request.  You can also pass in any override fields after the request.

```
	MyModel.createFromRequest(request, owner=request.user)
```

`saveFromRequest(request, **kwargs)` - this allows you to pass a request object (normally a post) and save data to the model from that request.  You can also pass in any override fields after the request.

```
	mode_instance.saveFromRequest(request, modified_by=request.user)
```

#### Other Helper Methods

`getFromRequest(cls, model_name)` - @classmethod - attempts to get the model from a request, check for the classname and classname+ "_id" in the REQUEST params.


`restGetModel(app_name, model_name)` - @staticmethod - grab Model class by app and model name.

`restGetGenericModel(self, fieldname)` - grab Model class by app and model name.

`restGetGenericRelation(self, fieldname)` - grab Model class by app and model name.

## Returning JSON Graph

Graphs can easily be built automatically from your models by setting the appropriate RestMeta properties.

`getGraph(name)` - @classmethod - Specify the name of the graph you want to return.

### RestMeta

This is a Property class you add to your models to define your graphs.

By default a graph will return just the fields with no recurse into of Foreign models.

