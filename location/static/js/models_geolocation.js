Models.GeoTrack = Backbone.Model.extend({
	urlRoot: '/rpc/location/track',

	getTracks: function() {

	}
});

Models.GeoPosition = Backbone.Model.extend({
	urlRoot: '/rpc/location/track'
});

Collections.GeoPosition = Backbone.Collection.extend({
	Model: Models.GeoPosition,

	url: function() {
		return "/rpc/location/track/" + this.options.id;
	},

	fetchLatest: function(options, now) {
		var pos = this.getCurrentPosition();
		if (pos) {
			this.params.size = 5000;
			this.params.last_pos_time = pos.get("created");
		}
		if (this.ttl > 0) {
			this.fetchIfStale(now, options);
		} else {
			this.fetch(options);
		}
		
	},

	getTracks: function() {
		return this;
	},

	getCurrentPosition: function() {
		if (this.length) {
			return this.at(this.length - 1);
		}
		return null;
	}
});
