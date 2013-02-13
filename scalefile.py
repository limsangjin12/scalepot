from api import *

@scale_out('worker')
def scale_out_worker(instance):
    print 'worker scaled out'

@scale_down('worker')
def scale_down_worker(instance):
    print 'worker scaled down'
