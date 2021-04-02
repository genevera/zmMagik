from colorama import init, Fore, Style
from shapely.geometry import Polygon
import cv2
import dateparser
import configargparse
import numpy as np
from datetime import datetime, timedelta
import re


import zmMagik_helpers.globals as g
def parse_args():
    ap = configargparse.ArgParser()
    ap.add_argument("-c", "--config", is_config_file=True, help="configuration file")
    ap.add_argument("-i", "--input", help="input video to search")
    ap.add_argument("--find", help="image to look for (needs to be same size/orientation as in video)")
    ap.add_argument("--mask", help="polygon points of interest within video being processed")
    ap.add_argument("--skipframes", help="how many frames to skip", type=int, default=1)
    ap.add_argument("--trailframes", help="how many frames to write after relevant frame", type=int, default=10)
    ap.add_argument("--blenddelay", help="how much time to wait in seconds before blending next event", type=int,
                    default=2)
    ap.add_argument("--fps", help="fps of video, to get timing correct", type=int)
    ap.add_argument("--threshold",
                    help="Only for background extraction. a number between 0 to 1 on accuracy threshold. 0.7 or above required",
                    type=float_71, default=0.7)
    ap.add_argument("--confidence", help="Only for YOLO. a number between 0 to 1 on minimum confidence score",
                    type=float_01, default=0.6)
    ap.add_argument("-a", "--all", action='store_true', help="process all frames, don't stop at first find")
    ap.add_argument("-w", "--write", action='store_true',
                    help="create video with matched frames. Only applicable for --find")
    ap.add_argument("--interactive", action='store_true',
                    help="move to next frame after keypress. Press 'c' to remove interactive")

    ap.add_argument("--eventid", help="Event id")
    ap.add_argument("--username", help="ZM username")
    ap.add_argument("--password", help="ZM password")
    ap.add_argument("--portal", help="ZM portal")
    ap.add_argument("--apiportal", help="ZM API portal")
    ap.add_argument("--detection_type", help="Type of detection for blending", default="background_extraction")
    ap.add_argument("--config_file", help="Config file for ML based detection with full path")
    ap.add_argument("--weights_file", help="Weights file for ML based detection with full path")
    ap.add_argument("--labels_file", help="labels file for ML based detection with full path")
    ap.add_argument("--meta_file", help="meta file for Yolo when using GPU mode")

    ap.add_argument('--gpu', nargs='?', default=False, const=True, type=str2bool,
                    help='enable GPU processing. Needs libdarknet.so compiled in GPU mode')

    ap.add_argument("--from", help="arbitrary time range like '24 hours ago' or formal dates")
    ap.add_argument("--to", help="arbitrary time range like '2 hours ago' or formal dates")
    ap.add_argument("--monitors", help="comma separated list of monitor IDs to search")
    ap.add_argument("--resize", help="resize factor (0.5 will halve) for both matching template and video size",
                    type=float)
    ap.add_argument("--dumpjson", nargs='?', default=False, const=True, type=str2bool,
                    help="write analysis to JSON file")
    #
    ap.add_argument("--annotate", nargs='?', const=True, default=False, type=str2bool,
                    help="annotates all videos in the time range. Only applicable if using --from --to or --eventid")
    #
    ap.add_argument("--blend", nargs='?', const=True, default=False, type=str2bool,
                    help="overlay all videos in the time range. Only applicable if using --from --to or --eventid")
    ap.add_argument("--detectpattern", help="which objects to detect (supports regex)", default=".*")
    ap.add_argument("--relevantonly", nargs='?', const=True, default=True, type=str2bool,
                    help="Only write frames that have detections")
    #
    ap.add_argument("--drawboxes", nargs='?', const=True, default=False, type=str2bool,
                    help="draw bounding boxes aroun objects in final video")
    #
    ap.add_argument("--minblendarea",
                    help="minimum area in pixels to accept as object of interest in forgeground extraction. Only applicable if using--blend",
                    type=float, default=1500)
    ap.add_argument("--fontscale", help="Size of font scale (1, 1.5 etc). Only applicable if using--blend", type=float,
                    default=1)
    #
    ap.add_argument("--download", nargs='?', const=True, type=str2bool,
                    help="Downloads remote videos first before analysis. Seems some openCV installations have problems with remote downloads",
                    default=True)
    #
    ap.add_argument("--display", nargs='?', const=True, default=False, type=str2bool,
                    help="displays processed frames. Only applicable if using --blend")
    #
    ap.add_argument("--show_progress", nargs='?', const=True, default=True, type=str2bool,
                    help="Shows progress bars")
    #
    ap.add_argument("--objectonly", nargs='?', const=True, default=False, type=str2bool,
                    help="Only process events where objects are detected. Only applicable if using --blend")
    ap.add_argument("--minalarmframes", help="how many alarmed frames for an event to be selected", type=int,
                    default=None)
    ap.add_argument("--maxalarmframes", help="how many alarmed frames for an event to be skipped", type=int,
                    default=None)
    ap.add_argument("--duration", help="how long (in seconds) to make the video", type=int, default=0)
    #
    ap.add_argument("--balanceintensity", nargs='?', const=True, default=False, type=str2bool,
                    help="If enabled, will try and match frame intensities - the darker frame will be aligned to match the brighter one. May be useful for day to night transitions, or not :-p. Works with --blend")
    #
    ap.add_argument('--present', nargs='?', default=True, const=True, type=str2bool,
                    help='look for frames where image in --match is present')
    ap.add_argument('--sequential', nargs='?', default=True, const=True, type=str2bool, help='Process events'
                                                                                                   'per monitor (i.e. you specify 2 monitors, it does the events for 1 monitor first, then the next monitor')
    try:
        g.args = vars(ap.parse_args())
    except Exception as e:
        print('error ConfigArgParse - {}'.format(e))
    process_config()

def float_01(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError('Float {} not in range of 0.1 to 1.0'.format(x))
    return x

def float_71(x):
    x = float(x)
    if x < 0.7 or x > 1.0:
        raise argparse.ArgumentTypeError('Float {} not in range of 0.7 to 1.0'.format(x))
    return x
#https://stackoverflow.com/a/43357954/1361529
def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def hist_match(source, template):
#https://stackoverflow.com/questions/32655686/histogram-matching-of-two-images-in-python-2-x
    olddtype = source.dtype
    oldshape = source.shape
    source = source.ravel()
    template = template.ravel()

    s_values, bin_idx, s_counts = np.unique(source, return_inverse=True,
                                            return_counts=True)
    t_values, t_counts = np.unique(template, return_counts=True)
    s_quantiles = np.cumsum(s_counts).astype(np.float64)
    s_quantiles /= s_quantiles[-1]
    t_quantiles = np.cumsum(t_counts).astype(np.float64)
    t_quantiles /= t_quantiles[-1]
    interp_t_values = np.interp(s_quantiles, t_quantiles, t_values)
    interp_t_values = interp_t_values.astype(olddtype)

    return interp_t_values[bin_idx].reshape(oldshape)

def init_colorama():
    init()

def secure_string(str):
    return re.sub(r'(((pass)(?:word)?)|(auth)|(token))=([^&/?]*)',r'\1=***',str.lower())    

def str2arr(str):
   ret = np.array(str.replace(' ',',').split(','),dtype=int).reshape(-1,2)
   return (ret)

def bold_print(text):
    print (Style.RESET_ALL+Style.BRIGHT+text+Style.RESET_ALL)

def dim_print(text):
    print (Style.RESET_ALL+Style.DIM+text+Style.RESET_ALL)

def success_print(text):
    print (Style.RESET_ALL+Fore.GREEN+text+Style.RESET_ALL)

def fail_print(text):
    print (Style.RESET_ALL+Fore.RED+text+Style.RESET_ALL)

def process_config():
    if not g.args['input'] and not g.args['eventid'] and not g.args['from'] and not g.args['to']:
        fail_print ('Error: You either need to specify an input video, an event id, or a timeline')
        exit(1)
    if g.args['eventid'] and not ( g.args['username'] and g.args['password'] and g.args['portal'] ):
        fail_print ('Error: If you specify an event ID, you MUST specify username,password and portal')
        exit(1)
    if (g.args['from'] or g.args['to']) and not ( g.args['username'] and g.args['password'] and g.args['portal'] ):
        fail_print ('Error: If you specify a timeline you MUST specify username,password and portal')
        exit(1)    
    if g.args['mask']:
        parr = str2arr(g.args['mask'])
        if g.args['resize']:
            resize = g.args['resize']
            parr =(parr*resize).astype(int)
        g.raw_poly_mask = parr
        g.poly_mask = Polygon(parr)
    
    if g.args['find']:
        g.template = cv2.imread(g.args['find'])
        if g.args['resize']:
            resize = g.args['resize']
        if g.args['resize']:
            rh, rw, rl = g.template.shape
            g.template = cv2.resize(g.template, (int(rw*resize), int(rh*resize)))
        g.template = cv2.cvtColor(g.template, cv2.COLOR_BGR2GRAY)

    if g.args['monitors']:
        g.mon_list = [int(item) for item in g.args['monitors'].split(',')]

    if g.args['minblendarea']:
        g.min_blend_area = g.args['minblendarea']

    if not g.args['find'] and not g.args['blend'] and not g.args['annotate']:
        fail_print('You need to specify one of  --find or --blend or --annotate')
        exit(1)


def write_text(frame=None, text=None, x=None,y=None, W=None, H=None, adjust=False):
    (tw, th) = cv2.getTextSize(text, cv2.FONT_HERSHEY_PLAIN, fontScale=g.args['fontscale'], thickness=2)[0]
    loc_x1 = x
    loc_y1 = y - th - 4
    loc_x2 = x + tw + 4
    loc_y2 = y

    if adjust:
        if not W or not H:
            fail_print('cannot auto adjust text as W/H  not provided')
        else:
            if loc_x1 + tw > W:
                loc_x1 = max (0, loc_x1 - (loc_x1+tw - W))
            if loc_y1 + th > H:
                loc_y1 = max (0, loc_y1 - (loc_y1+th - H))

    cv2.rectangle(frame, (loc_x1, loc_y1), (loc_x1+tw+4,loc_y1+th+4), (0,0,0), cv2.FILLED)
    cv2.putText(frame, text, (loc_x1+2, loc_y2-2), cv2.FONT_HERSHEY_PLAIN, fontScale=g.args['fontscale'], color=(255,255,255), thickness=1)
    return loc_x1, loc_y1, loc_x1+tw+4,loc_y1+th+4

    
