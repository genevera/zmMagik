
'''
    To search for objects:
        python ./magik.py  --find trash.jpg --username <user> --password <password> --portal https:/<portal>/zm --write --from "may 28 1pm" --to "may 28 5pm" --monitors 11,14 --no-present --skipframes=5
    To create a video blend within a time period:
    python ./magik.py  --username <user> --password <passwd> --portal https://<portal>/zm  --monitors <mid>   --from "jun 1, 9:58am" --to "jun 1, 10:06a"  --blend --objectonly --display  --skipframes=5 --mask="197,450 1276,463 1239,710 239,715"

The mask option filters blend matches only for that area
'''

import configargparse
import cv2
import numpy as np
import time
import os
import sys
from datetime import datetime, timedelta
import json
import dateparser
import pyzm
import pyzm.api as zmapi
if sys.version_info < (3, 0):
    sys.stdout.write("Sorry, this script requires Python 3.x, not Python 2.x\n")
    sys.exit(1)
import zmMagik_helpers.utils as utils
import zmMagik_helpers.globals as g
import zmMagik_helpers.blend as zmm_blend
import zmMagik_helpers.annotate as zmm_annotate
import zmMagik_helpers.search as zmm_search
import zmMagik_helpers.log as log


def remove_input(input_file=None):
    try:
        os.remove(input_file) # cleanup
    except:
        pass


def handoff(mo_id, ev_id, st_tm):
    global delay, in_file
    try:
        if g.args['blend']:
            res = zmm_blend.blend_video(input_file=in_file, out_file=g.out_file, eid=ev_id,
                                        mid=mo_id, starttime=st_tm,
                                        delay=delay)
            delay = delay + g.args['blenddelay']
        elif g.args['annotate']:
            res = zmm_annotate.annotate_video(input_file=in_file, eid=ev_id,
                                              mid=mo_id,
                                              starttime=st_tm)
        elif g.args['find']:
            res = zmm_search.search_video(input_file=in_file, out_file=g.out_file, eid=ev_id,
                                          mid=mo_id)
        else:
            raise ValueError('No support for mixing modes or you\'re trying an unknown mode')
    except IOError as e:
        utils.fail_print('ERROR: {}'.format(e))
    remove_input(in_file)


# colorama
utils.init_colorama()
# if running on a host without ZM pyzm logger throws errors looking for zm.conf, fix it
try:
    import pyzm.ZMLog as zmlog
    zmlog.init(name='zmMagik')
except ImportError as e:
    print('Could not import ZMLog, function will be disabled:' + str(e))
    zmlog = None
utils.parse_args()
if g.args['blend']:
    zmm_blend.blend_init()
if g.args['annotate']:
    zmm_annotate.annotate_init()
'''utils.dim_print('-----| Arguments to be used:')
for k, v in g.args.items():
    utils.dim_print('{}={}'.format(k, v))
print('\n')'''
s_time = time.time()
try:
    api_options = {
        'portalurl': g.args['portal'],
        'apiurl': g.args['apiportal'],
        'user': g.args['username'],
        'password': g.args['password'],
        'logger': zmlog,  # causes an error if host doesnt have /etc/zm/zm.conf, fix in pyzm?
    }
    import traceback
    import time
    zmapi = zmapi.ZMApi(options=api_options)
except Exception as e:
    print('Error initing zmAPI: {}'.format(str(e)))
    print(traceback.format_exc())
    exit(1)

try:
    event_filter = {}
    if g.args['eventid']:
        event_filter['event_id'] = g.args['eventid']
    if g.args['from']:
        event_filter['from'] = g.args['from']
    if g.args['to']:
        event_filter['to'] = g.args['to']
    if g.args['minalarmframes']:
        event_filter['min_alarmed_frames'] = g.args['minalarmframes']
    if g.args['maxalarmframes']:
        event_filter['max_alarmed_frames'] = g.args['maxalarmframes']
    if g.args['objectonly']:
        event_filter['object_only'] = g.args['objectonly']
except Exception as e:
    print('ERROR setting event_filter keys - {}'.format(e))
    pass
mons = g.mon_list
mon_events = {}
print('mons = {}'.format(mons))
#if only an eventid is passed we need to create a fake monitor for the loop, we are past filtering so dont bother
if not mons and g.args['eventid']:
    mons = [99673364559927652340123635241]
for m in mons:
    if mons[0] == 99673364559927652340123635241:
        cam_events = zmapi.events(options=event_filter)
    else:
        event_filter['mid'] = m
        cam_events = zmapi.events(options=event_filter)
    print('Found {} event(s) with filter: {}'.format(len(cam_events.list()), event_filter))
    cnt = 0
    # loop through the events now and extract info
    for e in cam_events.list():
        cnt += 1
        mon_events[e.id()] = [ e.id(), e.monitor_id(), e.start_time(), e.get_video_url()]
delay = 0
cnt = 0
event_f = {}
if not g.args['sequential']:
    if g.args['blend']:
        utils.fail_print('Mixing Events across Monitors, unexpected results may occur when blending')
        utils.fail_print('This would be useful if you have a camera defined with 2 or more monitors...')
    # sort list by event # (should be in correct order, if not I will try start time converted to epoch then sorted)
    # however start time seems to be only down to second resolution.... so..... also multiserver? or pyzm handles that?
    sorted_mon = []
    print('')
    for s_e in sorted(mon_events, reverse=True):
        sorted_mon.append(mon_events[s_e])
    #print('sorted_mon LEN ({}) = {}'.format(len(sorted_mon), sorted_mon))
    for s_event in sorted_mon:
        cnt += 1
        in_file = s_event[3]
        if g.args['download']:
            import urllib.request
            urllib.request.urlretrieve(s_event[3], str(s_event[0]) + '-video.mp4')
            in_file = str(s_event[0]) + '-video.mp4'
        print('\n==============| Processing Event:{} for Monitor: {} ({} of {})|============='.format(
            s_event[0], s_event[1], cnt, len(sorted_mon)))
        g.out_file = 'analyzed-mID_' + str(s_event[1]) + '-Event-' + str(s_event[0]) + '.mp4'
        handoff(s_event[1], s_event[0], s_event[2])
else:
    utils.bold_print('Sequential mode active: processing events per monitor')
    for ay in mon_events.keys():
        print('mon_events = {}'.format(mon_events))
        cnt += 1
        in_file = mon_events[ay][3]
        if g.args['download']:
            import urllib.request
            urllib.request.urlretrieve(mon_events[ay][3], str(mon_events[ay][0]) + '-video.mp4')
            in_file = str(mon_events[ay][0]) + '-video.mp4'
        print('\n==============| Processing Event:{} for Monitor: {} ({} of {})|============='.format(
            mon_events[ay][0], mon_events[ay][1], cnt, len(mon_events)))
        g.out_file = 'analyzed-mID_' + str(mon_events[ay][1]) + '-Event-' + str(mon_events[ay][0]) + '.mp4'
        handoff(mon_events[ay][1], mon_events[ay][0], mon_events[ay][2])
end_time = time.time()
print('\nTotal time: {}s'.format(round(end_time - s_time, 2)))
if g.args['dumpjson']:
    if g.json_out:
        jf = 'analyzed-' + datetime.now().strftime("%m_%d_%Y_%H_%M_%S") + '.json'
        print('Writing output to {}'.format(jf))
        with open(jf, 'w') as jo:
            json.dump(g.json_out, jo)
