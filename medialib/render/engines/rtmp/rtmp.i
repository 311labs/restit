%module rtmp
%{
#include "librtmp/rtmp.h"
%}

%inline {

typedef struct sink {
	RTMP *ctx;
	char *url;
} sink;

typedef struct dump {
	RTMP *ctx;
	char *url;
	char *buf;
	int bufsize;
} dump;

static PyObject *last_err;
static char *last_errstr;

}

%exception {
	$action
	if (last_err) {
		PyErr_SetString(last_err, last_errstr);
		last_err = NULL;
		last_errstr = NULL;
		return NULL;
	}
}

%extend sink {
	%typemap(in) (const char *data, int len) {
		$1 = PyString_AsString($input);
		$2 = PyString_Size($input);
	}

	sink(const char *url) {
		sink *p;

		//RTMP_LogSetLevel(99);
		p = malloc(sizeof(sink));
		if (!p) {
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}
		p->url = strdup(url);
		if (!p->ctx) {
			free(p);
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}

		p->ctx = RTMP_Alloc();
		if (!p->ctx) {
			free(p->url);
			free(p);
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}
		RTMP_Init(p->ctx);
		if (!RTMP_SetupURL(p->ctx, p->url)) {
			last_err = PyExc_ValueError;
			last_errstr = "Invalid URL";
			RTMP_Free(p->ctx);
			free(p->url);
			free(p);
			return NULL;
		}
		RTMP_EnableWrite(p->ctx);
		if (!RTMP_IsConnected(p->ctx)) {
			errno = 0;
			if (!RTMP_Connect(p->ctx, NULL) || !RTMP_ConnectStream(p->ctx, 0)) {
				if (errno) {
					last_err = PyExc_OSError;
					last_errstr = strerror(errno);
				} else {
					last_err = PyExc_RuntimeError;
					last_errstr = "Cannot connect to URL";
				}
				RTMP_Free(p->ctx);
				free(p->url);
				free(p);
				return NULL;
			}
		}
		return p;
	}
	~sink() {
		if ($self->ctx) {
			if (RTMP_IsConnected($self->ctx)) {
				RTMP_Close($self->ctx);
			}
		}
		RTMP_Free($self->ctx);
		free($self->url);
		free($self);
	}
	void close() {
		if ($self->ctx && RTMP_IsConnected($self->ctx)) {
			RTMP_Close($self->ctx);
		}
	}
	int write(const char *data, int len) {
		int ret;
		ret = RTMP_Write($self->ctx, data, len);
		if (ret < 0) {
			last_err = PyExc_OSError;
			last_errstr = strerror(errno);
		}
		return ret;
	}
}

%extend dump {
	dump(const char *url) {
		dump *p;

		p = malloc(sizeof(dump));
		if (!p) {
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}
		p->buf = NULL;
		p->bufsize = 0;
		p->url = strdup(url);
		if (!p->ctx) {
			free(p);
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}

		p->ctx = RTMP_Alloc();
		if (!p->ctx) {
			free(p->url);
			free(p);
			last_err = PyExc_MemoryError;
			last_errstr = "Out of memory";
			return NULL;
		}
		RTMP_Init(p->ctx);
		if (!RTMP_SetupURL(p->ctx, p->url)) {
			last_err = PyExc_ValueError;
			last_errstr = "Invalid URL";
			RTMP_Free(p->ctx);
			free(p->url);
			free(p);
			return NULL;
		}
		if (!RTMP_IsConnected(p->ctx)) {
			errno = 0;
			if (!RTMP_Connect(p->ctx, NULL) || !RTMP_ConnectStream(p->ctx, 0)) {
				if (errno) {
					last_err = PyExc_OSError;
					last_errstr = strerror(errno);
				} else {
					last_err = PyExc_RuntimeError;
					last_errstr = "Cannot connect to URL";
				}
				RTMP_Free(p->ctx);
				free(p->url);
				free(p);
				return NULL;
			}
		}
		return p;
	}
	~dump() {
		if ($self->ctx) {
			if (RTMP_IsConnected($self->ctx)) {
				RTMP_Close($self->ctx);
			}
		}
		RTMP_Free($self->ctx);
		if ($self->buf) free($self->buf);
		free($self->url);
		free($self);
	}
	void close() {
		if ($self->ctx && RTMP_IsConnected($self->ctx)) {
			RTMP_Close($self->ctx);
		}
	}
	PyObject* read(int len) {
		int ret;
		if (len > $self->bufsize) {
			if ($self->buf) free($self->buf);
			$self->buf = malloc(len);
			if (!$self->buf) {
				$self->bufsize = 0;
				last_err = PyExc_MemoryError;
				last_errstr = "Out of memory";
				return NULL;
			}
			$self->bufsize = len;
		}
		ret = RTMP_Read($self->ctx, $self->buf, len);
		if (ret < 0) {
			last_err = PyExc_OSError;
			last_errstr = strerror(errno);
			return NULL;
		}
		return PyString_FromStringAndSize($self->buf, ret);
	}
}

