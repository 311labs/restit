# Incident Framework

## Rules

Rule defines a set of checks that will create an incident from an incoming event.

There is no subscriptions.  Group with kind incident are created as buckets.
When a rule is triggered it will create a new incident

the incident will be assigned to the rule.group
the incident priority will be assigned to the rule.priority

Events can be bundled into a single Incident by setting bundle=<minutes>.  
So if bundle is set to 60 then for 60 minutes after the first event all events will get 
added to to same incident.

### Rule Actions

By default a rule will just create an incident and notify all members in rules group

You can also set a rule to ignore any hits:
action = "ignore"

or you can fire off a Task

action = "task:APP_NAME:FNAME:CHANNEL"
action = "task:account:lock_account_incident:tq_app_handler"


## Event

### Level

1 is the highest


```
{
	 "description": "Critical Test Event",
	 "hostname": "r1",
	 "details": "A critical event occurred on r1 running blah blah",
	 "level": 7,
	 "category": "prepaid.event",
	 "metadata": {
		"error_stack": "....."
	 }
}
```