INC=$(python -c 'import  distutils.sysconfig; print distutils.sysconfig.get_python_inc()')

all: _rtmp.so

rtmp_wrap.c:	rtmp.i
	swig -python rtmp.i

_rtmp.so:	rtmp_wrap.c
	$(CC) -shared -fPIC -I/usr/local/include -I`python -c 'import  distutils.sysconfig; print distutils.sysconfig.get_python_inc()'` rtmp_wrap.c -L/usr/local/lib -lrtmp -o _rtmp.so

clean:
	rm -f *~ _rtmp.so rtmp_wrap.c rtmp.py*
