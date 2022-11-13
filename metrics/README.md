
Is based on...
https://django-redis-metrics.readthedocs.io/en/latest/

# Usage

Use the `metric` shortcut to start recording metrics.

```python
from redis_metrics import metric

# Increment the metric by one
metric('new-user-signup')

# Increment the metric by some other number
metric('new-user-signup', 4)
```

Metrics can also be categorized. To record a metric and add it to a category, specify a `category` keyword parameter

```python
# Increment the metric, and add it to a category
metric('new-user-signup', category="User Metrics")
```

Metrics can also expire after a specified number of seconds

```python
# The 'foo' metric will expire in 5 minutes
metric('foo', expire=300)
```

You can also *reset* a metric with the `set_metric` function. This will replace any existing values for the metric, rather than incrementing them. It’s api is similar to `metric`’s.

```python
from redis_metrics import set_metric

# Reset the Download count.
set_metric("downloads", 0)
```

## Gauges

There are also `gauge`’s. A `gauge` is great for storing a *cumulative* value, and when you don’t care about keeping a history for the metric. In other words, a gauge gives you a snapshot of some current value.

```python
from redis_metrics import gauge

# Create a gauge
gauge('total-downloads', 0)

# Update the gauge
gauge('total-downloads', 9999)
```

## The R class

There’s also an `R` class which is a lightweight wrapper around `redis`. You can use it directly to set metrics or gauges and to retrieve data.

```python
>>> from redis_metrics.models import R
>>> r = R()
>>> r.metric('new-user-signup')
>>> r.get_metric('new-user-signup')
{
    'second': 0,
    'minute': 0,
    'hour': 1,
    'day': '29',
    'month': '29',
    'week': '29',
    'year': '29'
}

# list the slugs you've used to create metrics
>>> r.metric_slugs()
set(['new-user-signup', 'user-logins'])

# Get metrics for multiple slugs
>>> r.get_metrics(['new-user-signup', 'user-logins'])
[
    {'new-user-signup': {
        'second': '0', 'minute': '0', 'hour': '1',
        'day': '7', 'month': '7', 'week': '7', 'year': '7'}},
    {'user-logins':
        'second': '0', 'minute': '0', 'hour': '1',
        'day': '7', 'month': '7', 'week': '7', 'year': '7'}},
]

# Delete a metric
>>> r.delete_metric("app-errors")
```

