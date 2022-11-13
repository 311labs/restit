Models.Product = Backbone.Model.extend({
	urlRoot: "/rpc/pushit/product",

	display_label: function() {
		return this.get("name") + " " + this.get("current.version_str");
	}
});

Models.Release = Backbone.Model.extend({
    urlRoot: "/rpc/pushit/release"
});

Collections.Product = Backbone.Collection.extend({
    Model: Models.Product,
});

Collections.Release = Backbone.Collection.extend({
    Model: Models.Release,
});