Collections.AuditLogs = Backbone.Collection.extend({
	url: '/rpc/auditlog/plog',
});

Collections.PersistantLogs = Backbone.Collection.extend({
	url: '/rpc/auditlog/plog',
});