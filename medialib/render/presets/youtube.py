
from medialib import youtube

from django.conf import settings

PresetConfig = {
    'name':		'YouTube',
    'description':	'Upload to YouTube',
    'stage':	101,
    'default_use':	'youtube',
    'applicable_kinds': 'VAS',
    'parameters': {
        'access_token': {
            'description':	'Access Token',
            'required':	True,
            'kind':		'S',
            'configurable':	True,
        },
        'categories_scheme': {
            'description':	'Category scheme XML URL',
            'required':	False,
            'kind':		'S',
            'configurable':	False,
            'value':	'http://gdata.youtube.com/schemas/2007/categories.cat',
        },
        'title': {
            'description':	'Video Title Override',
            'required':	False,
            'kind':		'S',
            'configurable':	True,
        },
        'category': {
            'description':	'Category Name',
            'required':	True,
            'kind':		'C',
            'configurable':	True,
            'choices':	'Film,Autos,Music,Animals,Sports,Travel,Games,Comedy,People,News,Entertainment,Education,Howto,Nonprofit,Tech',
        },
        'description': {
            'description':	'Description Text',
            'required':	False,
            'kind':		'S',
            'configurable':	True,
        },
        'keywords': {
            'description':	'Keywords',
            'required':	False,
            'kind':		'S',
            'configurable':	False,
        },
        'private': {
            'description':	'Set private?',
            'required':	True,
            'kind':		'B',
            'configurable':	True,
        },
    },
}


categories = {
    'Animals': 'Pets & Animals',
    'Autos': 'Autos & Vehicles',
    'Comedy': 'Comedy',
    'Education': 'Education',
    'Entertainment': 'Entertainment',
    'Film': 'Film & Animation',
    'Games': 'Gaming',
    'Howto': 'Howto & Style',
    'Music': 'Music',
    'News': 'News & Politics',
    'Nonprofit': 'Nonprofits & Activism',
    'People': 'People & Blogs',
    'Sports': 'Sports',
    'Tech': 'Science & Technology',
    'Travel': 'Travel & Events',
}


def render(item, renditiondef, params):
    rendition = youtube.uploadMediaItem(params["access_token"], item, renditiondef, params)
