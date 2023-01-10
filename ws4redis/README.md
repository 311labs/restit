# Websocket HOWTO

## authentication

### JWT

Requires an existing JWT token that has gone through authentication process via rest

```json
{
    "action": "auth",
    "kind": "jwt",
    "token": "..."
}
```

### Alternative

Using the settings WS4REDIS_AUTHENTICATORS parameter you can configure alternate authentication flows.

```
WS4REDIS_AUTHENTICATORS = {
    "mymodel": "myapp.MyModel"
}
```

```json
{
    "action": "auth",
    "kind": "mymodel",
    "token": "..."
}
```


## Subscribe

```json
{
    "action": "subscribe",
    "channel": "group",
    "pk": 3,
}
```

### Security

In settins WS4REDIS_CHANNELS, map your channel to a model.
The model should have a classmethod for canSubscribeTo that returns a list of pk they can subscribe to.


## UnSubscribe

```json
{
    "action": "unsubscribe",
    "channel": "group",
    "pk": 3,
}
```


## Publish / Send To

```json
{
    "action": "publish",
    "channel": "group",
    "pk": 3,
    "message": "..."
}
```

### Security

In settins WS4REDIS_CHANNELS, map your channel to a model.
The model should have a classmethod for canPublishTo that returns a list of pk they can publish to.


## Custom Messages

If an unknown action is sent with a channel then the framework will call onWS4RedisMessage on the channel model.


