var search_xhr = null;
var next_page = null;
var search_loaded = 0;
var search_change = null;
var last_q = null;

var MediaLibDialog = {
	_click: function(div, item) {
		var item_type;
		if (item.kind == 'I') {
			item_type = 'image';
		} else if (item.kind == 'V') {
			item_type = 'video';
		} else {
			item_type = 'unknown';
		}
		var width = item.width;
		var height = item.height;
		if (width && width > 400) {
			height = height * 400 / width;
			width = 400;
		}
		if (height && height > 300) {
			width = width * 300 / height;
			height = 300;
		}
		if (!width) {
			width = "";
		}
		if (!height) {
			height = "";
		}
		tinyMCEPopup.editor.execCommand('mceInsertContent', false, '<img class="medialib medialib_' + item_type + ' medialib_id_' + item.id + '" width="' + width + '" height="' + height + '" src="' + item.still + '"/>');
		tinyMCEPopup.close();
	},
	_mouseIn: function(div, item) {
		var img = $(div).find('img.thumb');
		if (item.thumbnail_animated == item.thumbnail) {
			img.attr('src', item.image);
		} else {
			img.attr('src', item.thumbnail_animated);
		}
	},
	_mouseOut: function(div, item) {
		var img = $(div).find('img.thumb');
		img.attr('src', item.thumbnail);
	},
	_onScroll: function() {
		if (search_xhr || !next_page) { return; }
		var cur = $(window).scrollTop() + $(window).height();
		var maxh = $('body').height();
		if (cur + 310 > maxh) {
			MediaLibDialog._search(null);
		}
	},
	_onChange: function() {
		if ($('#search_input').val() === last_q) { return; }
		if (search_change) {
			clearTimeout(search_change);
		}
		search_change = null;
		if (search_xhr) {
			search_xhr.abort();
			search_xhr = null;
		}
		next_page = null;
		$('#content').empty();
		MediaLibDialog._search($('#search_input').val());
	},
	_search: function(q) {
		if (search_xhr) {
			search_xhr.abort();
			search_xhr = null;
		}
		var data;
		if (q !== null) {
			data = {
				q: q,
				sort: '-id'
			};
			search_loaded = 0;
			last_q = q;
			$('#search_result').text('Loading...');
		} else if (next_page) {
			data = next_page;
		} else {
			return;
		}
		$('#status_loading').show();
		next_page = null;
		search_xhr = TWIN.medialib.search(data,
			{
				onSuccess: function(response) {
					var content = $('#content');
					$.each(response.data, function(idx, item) {
						var div = $('<div/>')
							.addClass('mediaitem')
							.data('data', item)
							.hover(
								function() {MediaLibDialog._mouseIn(this, item);},
								function() {MediaLibDialog._mouseOut(this, item);}
							)
							.click(function() {
								MediaLibDialog._click(this, item);
								return false;
							})
							.appendTo(content);
						var holder = $('<div/>')
							.addClass('imgholder')
							.appendTo(div);
							
						$('<img/>')
							.addClass('thumb')
							.attr('src', item.thumbnail)
							.attr('alt', item.name)
							.appendTo(holder);
						var details = $('<div/>')
							.addClass('details')
							.appendTo(holder);
						$('<div/>')
							.append($('<span class="label"/>').text('Owner:'))
							.append($('<span class="data"/>').text(item.owner.username))
							.appendTo(details);
						$('<div/>')
							.append($('<span class="label"/>').text('Created:'))
							.append($('<span class="data"/>').text(TWIN.utils.humanDate(item.created)))
							.appendTo(details);
						var icontype;
						if (item.kind == 'V') {
							icontype = 'media';
						} else if (item.kind == 'I') {
							icontype = 'image';
						} else {
							icontype = 'generic';
						}
						$('<img/>')
							.addClass('typeicon')
							.attr('src', '../../../../img/icon-' + icontype + '.gif')
							.appendTo(div);
						$('<div/>')
							.addClass('descr')
							.text(item.name)
							.appendTo(div);
					});
					search_loaded += response.data.length;
					$('#search_result').text(response.count + ' results (' + search_loaded + ')');
					search_xhr = null;
					$('#status_loading').hide();
					if (response.data.length && response.page_next) {
						next_page = data;
						next_page.page = response.page_next;
					}
				}, onFail: function(ret, textstatus, errorthrown) {
					$('#search_result').text('Load failed');
					search_xhr = null;
					$('#status_loading').hide();
				}	
			}
		);
	},
	
	init: function() {
		$('#search_input').focus();
		$('#search_form').submit(function() {
			MediaLibDialog._onChange();
			return false;
		});
		$('#search_input').keydown(function() {
			if (search_change) {
				clearTimeout(search_change);
			}
			search_change = setTimeout(MediaLibDialog._onChange, 500);
		});
		$('#search_input').keypress(function(e) {
			var code = e.keyCode || e.which;
			if (code == 34) { // page down
				$(window).scrollTop($(window).scrollTop()+$(window).height()-40);
				return false;
			} else if (code == 33) { // page up
				$(window).scrollTop($(window).scrollTop()-$(window).height()+40);
				return false;
			} else if (code == 36) { // home
				$(window).scrollTop(0);
				return false;
			} else if (code == 35) { // end
				$(window).scrollTop($('body').height());
				return false;
			} else if (code == 40) { // down
				$(window).scrollTop($(window).scrollTop()+50);
				return false;
			} else if (code == 38) { // up
				$(window).scrollTop($(window).scrollTop()-50);
				return false;
			} else {
				return true;
			}
		});
		MediaLibDialog._onChange();
		$(window).scroll(MediaLibDialog._onScroll);
		MediaLibDialog._onScroll();
	}
};

tinyMCEPopup.onInit.add(MediaLibDialog.init, MediaLibDialog);

