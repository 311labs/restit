/**
 * editor_plugin_src.js
 *
 * Twin Medialib TinyMCE plugin
 */

(function() {
	tinymce.create('tinymce.plugins.MediaLibPlugin', {
		init : function(ed, url) {
			ed.addCommand('mceMedialib', function() {
				ed.windowManager.open({
					file : url + '/medialib.html',
					width : 690 + parseInt(ed.getLang('medialib.delta_width', 0)),
					height : 385 + parseInt(ed.getLang('medialib.delta_height', 0)),
					inline : 1,
					scrollbars: true
				}, {
					plugin_url : url
				});
			});

			// Register example button
			ed.addButton('medialib', {
				title : 'Media Library',
				cmd : 'mceMedialib',
				'class': 'mce_image'
			});

			// Add a node change handler, selects the button in the UI when a image is selected
//			ed.onNodeChange.add(function(ed, cm, n) {
//				cm.setActive('example', n.nodeName == 'IMG');
//			});
		},

		getInfo : function() {
			return {
				longname : 'Media Library',
				author : 'Twin Technologies',
				authorurl : 'http://www.twintechs.com',
				infourl : '//www.twintechs.com/',
				version : "1.0"
			};
		}
	});

	// Register plugin
	tinymce.PluginManager.add('medialib', tinymce.plugins.MediaLibPlugin);
})();
