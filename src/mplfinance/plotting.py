import matplotlib.dates  as mdates
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import pandas as pd
import numpy  as np
import copy
import io
import math
import warnings
import statistics as stat

from itertools import cycle
#from pandas.plotting import register_matplotlib_converters
#register_matplotlib_converters()

from mplfinance._utils import _construct_aline_collections
from mplfinance._utils import _construct_hline_collections
from mplfinance._utils import _construct_vline_collections
from mplfinance._utils import _construct_tline_collections
from mplfinance._utils import _construct_mpf_collections

from mplfinance._widths import _determine_width_config

from mplfinance._utils import _updown_colors
from mplfinance._utils import IntegerIndexDateTimeFormatter
from mplfinance._utils import _mscatter

from mplfinance import _styles

from mplfinance._arg_validators import _check_and_prepare_data, _mav_validator
from mplfinance._arg_validators import _process_kwargs, _validate_vkwargs_dict
from mplfinance._arg_validators import _kwarg_not_implemented, _bypass_kwarg_validation
from mplfinance._arg_validators import _hlines_validator, _vlines_validator
from mplfinance._arg_validators import _alines_validator, _tlines_validator
from mplfinance._arg_validators import _valid_panel_id

from mplfinance._panels import _build_panels
from mplfinance._panels import _set_ticks_on_bottom_panel_only

from mplfinance._helpers import _determine_format_string
from mplfinance._helpers import _list_of_dict
from mplfinance._helpers import _num_or_seq_of_num
from mplfinance._helpers import _adjust_color_brightness

VALID_PMOVE_TYPES = ['renko', 'pnf']

DEFAULT_FIGRATIO = (8.00,5.75)

def with_rc_context(func):
    '''
    This decoractor creates an rcParams context around a function, so that any changes
    the function makes to rcParams will be reversed when the decorated function returns
    (therefore those changes have no effect outside of the decorated function).
    '''
    def decorator(*args, **kwargs):
        with plt.rc_context():
            return func(*args, **kwargs)
    return decorator

def _warn_no_xgaps_deprecated(value):
    warnings.warn('\n\n ================================================================= '+
                  '\n\n   WARNING: `no_xgaps` is deprecated:'+
                  '\n     Default value is now `no_xgaps=True`'+
                  '\n     However, to set `no_xgaps=False` and silence this warning,'+
                  '\n     use instead: `show_nontrading=True`.'+
                  '\n\n ================================================================ ',
                  category=DeprecationWarning)
    return isinstance(value,bool)


def _valid_plot_kwargs():
    '''
    Construct and return the "valid kwargs table" for the mplfinance.plot() function.
    A valid kwargs table is a `dict` of `dict`s.  The keys of the outer dict are the
    valid key-words for the function.  The value for each key is a dict containing
    2 specific keys: "Default", and "Validator" with the following values:
        "Default"      - The default value for the kwarg if none is specified.
        "Validator"    - A function that takes the caller specified value for the kwarg,
                         and validates that it is the correct type, and (for kwargs with 
                         a limited set of allowed values) may also validate that the
                         kwarg value is one of the allowed values.
    '''

    vkwargs = {
        'columns'                   : { 'Default'     : ('Open', 'High', 'Low', 'Close', 'Volume'),
                                        'Validator'   : lambda value: isinstance(value, (tuple, list))
                                                                   and len(value) == 5
                                                                   and all(isinstance(c, str) for c in value) },
        'type'                      : { 'Default'     : 'ohlc',
                                        'Validator'   : lambda value: value in ('candle','candlestick','ohlc','ohlc_bars',
                                                                                'line','renko','pnf') },
 
        'style'                     : { 'Default'     : 'default',
                                        'Validator'   : lambda value: value in _styles.available_styles() or isinstance(value,dict) },
 
        'volume'                    : { 'Default'     : False,
                                        'Validator'   : lambda value: isinstance(value,bool) },
 
        'mav'                       : { 'Default'     : None,
                                        'Validator'   : _mav_validator },
        
        'renko_params'              : { 'Default'     : dict(),
                                        'Validator'   : lambda value: isinstance(value,dict) },

        'pnf_params'                : { 'Default'     : dict(),
                                        'Validator'   : lambda value: isinstance(value,dict) },
 
        'study'                     : { 'Default'     : None,
                                        'Validator'   : lambda value: _kwarg_not_implemented(value) }, 
 
        'marketcolors'              : { 'Default'     : None, # use 'style' for default, instead.
                                        'Validator'   : lambda value: isinstance(value,dict) },
 
        'no_xgaps'                  : { 'Default'     : True,  # None means follow default logic below:
                                        'Validator'   : lambda value: _warn_no_xgaps_deprecated(value) },
 
        'show_nontrading'           : { 'Default'     : False, 
                                        'Validator'   : lambda value: isinstance(value,bool) },
 
        'figscale'                  : { 'Default'     : 1.0, # scale base figure size up or down.
                                        'Validator'   : lambda value: isinstance(value,float) or isinstance(value,int) },
 
        'figratio'                  : { 'Default'     : DEFAULT_FIGRATIO, # aspect ratio; scaled to 8.0 height
                                        'Validator'   : lambda value: isinstance(value,(tuple,list))
                                                                      and len(value) == 2
                                                                      and isinstance(value[0],(float,int))
                                                                      and isinstance(value[1],(float,int)) },
 
        'figsize'                   : { 'Default'     : None,  # figure size; overrides figratio and figscale
                                        'Validator'   : lambda value: isinstance(value,(tuple,list))
                                                                      and len(value) == 2
                                                                      and isinstance(value[0],(float,int))
                                                                      and isinstance(value[1],(float,int)) },
 
        'linecolor'                 : { 'Default'     : None, # line color in line plot
                                        'Validator'   : lambda value: mcolors.is_color_like(value) },

        'title'                     : { 'Default'     : None, # Plot Title
                                        'Validator'   : lambda value: isinstance(value,str) },
 
        'ylabel'                    : { 'Default'     : 'Price', # y-axis label
                                        'Validator'   : lambda value: isinstance(value,str) },
 
        'ylabel_lower'              : { 'Default'     : None, # y-axis label default logic below
                                        'Validator'   : lambda value: isinstance(value,str) },
 
        'addplot'                   : { 'Default'     : None, 
                                        'Validator'   : lambda value: isinstance(value,dict) or (isinstance(value,list) and all([isinstance(d,dict) for d in value])) },
 
        'savefig'                   : { 'Default'     : None, 
                                        'Validator'   : lambda value: isinstance(value,dict) or isinstance(value,str) or isinstance(value, io.BytesIO) },
 
        'block'                     : { 'Default'     : True, 
                                        'Validator'   : lambda value: isinstance(value,bool) },
 
        'returnfig'                 : { 'Default'     : False, 
                                        'Validator'   : lambda value: isinstance(value,bool) },

        'return_calculated_values'  : {'Default': None,
                                       'Validator': lambda value: isinstance(value, dict) and len(value) == 0},

        'set_ylim'                  : {'Default': None,
                                       'Validator': lambda value: isinstance(value, (list,tuple)) and len(value) == 2 
                                                                  and all([isinstance(v,(int,float)) for v in value])},
 
        'set_ylim_panelB'           : {'Default': None,
                                       'Validator': lambda value: isinstance(value, (list,tuple)) and len(value) == 2 
                                                                  and all([isinstance(v,(int,float)) for v in value])},
 
        'hlines'                    : { 'Default'     : None, 
                                        'Validator'   : lambda value: _hlines_validator(value) },
 
        'vlines'                    : { 'Default'     : None, 
                                        'Validator'   : lambda value: _vlines_validator(value) },

        'alines'                    : { 'Default'     : None, 
                                        'Validator'   : lambda value: _alines_validator(value) },
 
        'tlines'                    : { 'Default'     : None, 
                                        'Validator'   : lambda value: _tlines_validator(value) },
       
        'panel_ratios'              : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,(tuple,list)) and len(value) <= 10 and
                                                                      all([isinstance(v,(int,float)) for v in value]) },

        'main_panel'                : { 'Default'     : 0,
                                        'Validator'   : lambda value: _valid_panel_id(value) },

        'volume_panel'              : { 'Default'     : 1,
                                        'Validator'   : lambda value: _valid_panel_id(value) },

        'num_panels'                : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,int) and value in range(1,10+1) },

        'datetime_format'           : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,str) },

        'xrotation'                 : { 'Default'     : 45,
                                        'Validator'   : lambda value: isinstance(value,(int,float)) },

        'axisoff'                   : { 'Default'     : False,
                                        'Validator'   : lambda value: isinstance(value,bool) },

        'closefig'                  : { 'Default'     : 'auto',
                                        'Validator'   : lambda value: isinstance(value,bool) },

        'fill_between'              : { 'Default'     : None,
                                        'Validator'   : lambda value: _num_or_seq_of_num(value) or 
                                                                     (isinstance(value,dict) and 'y1' in value and
                                                                       _num_or_seq_of_num(value['y1'])) },

        'tight_layout'              : { 'Default'     : False,
                                        'Validator'   : lambda value: isinstance(value,bool) },

        'width_adjuster_version'    : { 'Default'     : 'v1',
                                        'Validator'   : lambda value: value in ('v0', 'v1') },

        'scale_width_adjustment'    : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,dict) and len(value) > 0 },

        'update_width_config'       : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,dict) and len(value) > 0 },

        'return_width_config'       : { 'Default'     : None,
                                        'Validator'   : lambda value: isinstance(value,dict) and len(value)==0 },

        'saxbelow'                  : { 'Default'     : True,  # Issue#115 Comment#639446764
                                        'Validator'   : lambda value: isinstance(value,bool) },
    }

    _validate_vkwargs_dict(vkwargs)

    return vkwargs

###@with_rc_context
def plot( data, **kwargs ):
    """
    Given a Pandas DataFrame containing columns Open,High,Low,Close and optionally Volume
    with a DatetimeIndex, plot the data.
    Available plots include ohlc bars, candlestick, and line plots.
    Also provide visually analysis in the form of common technical studies, such as:
    moving averages, renko, etc.
    Also provide ability to plot trading signals, and/or addtional user-defined data.
    """

    config = _process_kwargs(kwargs, _valid_plot_kwargs())
    
    dates,opens,highs,lows,closes,volumes = _check_and_prepare_data(data, config)

    if config['type'] in VALID_PMOVE_TYPES and config['addplot'] is not None:
        err = "`addplot` is not supported for `type='" + config['type'] +"'`"
        raise ValueError(err)

    style = config['style']
    if isinstance(style,str):
        style = _styles._get_mpfstyle(style)

    if isinstance(style,dict):
        _styles._apply_mpfstyle(style)
    
    if config['figsize'] is None:
        w,h = config['figratio']
        r = float(w)/float(h)
        if r < 0.20 or r > 5.0:
            raise ValueError('"figratio" (aspect ratio)  must be between 0.20 and 5.0 (but is '+str(r)+')')
        default_scale = DEFAULT_FIGRATIO[1]/h
        h *= default_scale
        w *= default_scale
        base      = (w,h)
        figscale  = config['figscale']
        fsize     = [d*figscale for d in base]
    else:
        fsize = config['figsize']
    
    fig = plt.figure()
    fig.set_size_inches(fsize)

    if config['volume'] and volumes is None:
        raise ValueError('Request for volume, but NO volume data.')

    panels = _build_panels(fig, config)

    volumeAxes = panels.at[config['volume_panel'],'axes'][0] if config['volume'] is True else None

    fmtstring = _determine_format_string( dates, config['datetime_format'] )

    ptype = config['type'] 

    if config['show_nontrading']:
        formatter = mdates.DateFormatter(fmtstring)
        xdates = dates
    else:
        formatter = IntegerIndexDateTimeFormatter(dates, fmtstring)
        xdates = np.arange(len(dates))

    axA1 = panels.at[config['main_panel'],'axes'][0]

    # Will have to handle widths config separately for PMOVE types ??
    config['_width_config'] = _determine_width_config(xdates, config)


    rwc = config['return_width_config']
    if isinstance(rwc,dict) and len(rwc)==0:
        config['return_width_config'].update(config['_width_config'])
 

    collections = None
    if ptype == 'line':
        lw = config['_width_config']['line_width']
        axA1.plot(xdates, closes, color=config['linecolor'], linewidth=lw)
    else:
        collections =_construct_mpf_collections(ptype,dates,xdates,opens,highs,lows,closes,volumes,config,style)

    if ptype in VALID_PMOVE_TYPES:
        collections, new_dates, volumes, brick_values, size = collections
        formatter = IntegerIndexDateTimeFormatter(new_dates, fmtstring)
        xdates = np.arange(len(new_dates))

    if collections is not None:
        for collection in collections:
            axA1.add_collection(collection)

    mavgs = config['mav']
    if mavgs is not None:
        if isinstance(mavgs,int):
            mavgs = mavgs,      # convert to tuple 
        if len(mavgs) > 7:
            mavgs = mavgs[0:7]  # take at most 7
     
        if style['mavcolors'] is not None:
            mavc = cycle(style['mavcolors'])
        else:
            mavc = None

        # Get rcParams['lines.linewidth'] and scale it
        # according to the deinsity of data??

        for mav in mavgs:
            if ptype in VALID_PMOVE_TYPES:
                mavprices = pd.Series(brick_values).rolling(mav).mean().values
            else:
                mavprices = pd.Series(closes).rolling(mav).mean().values

            lw = config['_width_config']['line_width']
            if mavc:
                axA1.plot(xdates, mavprices, linewidth=lw, color=next(mavc))
            else:
                axA1.plot(xdates, mavprices, linewidth=lw)

    avg_dist_between_points = (xdates[-1] - xdates[0]) / float(len(xdates))
    if not config['tight_layout']:
        #print('plot: xdates[-1]=',xdates[-1])
        #print('plot: xdates[ 0]=',xdates[ 0])
        #print('plot: len(xdates)=',len(xdates))
        #print('plot: avg_dist_between_points =',avg_dist_between_points)
        minx = xdates[0]  - avg_dist_between_points
        maxx = xdates[-1] + avg_dist_between_points
    else:
        minx = xdates[0]  - (0.45 * avg_dist_between_points)
        maxx = xdates[-1] + (0.45 * avg_dist_between_points)

    if len(xdates) == 1:  # kludge special case
        minx = minx - 0.75
        maxx = maxx + 0.75
    if ptype not in VALID_PMOVE_TYPES:
        _lows  = lows
        _highs = highs
    else:
        _lows  = brick_values
        _highs = [brick+size for brick in brick_values]

    miny = np.nanmin(_lows)
    maxy = np.nanmax(_highs)
    #if len(xdates) > 1:
    #   stdy = (stat.stdev(_lows) + stat.stdev(_highs)) / 2.0
    #else:  # kludge special case
    #   stdy = 0.02 * math.fabs(maxy - miny)
    # print('minx,miny,maxx,maxy,stdy=',minx,miny,maxx,maxy,stdy)

    if config['set_ylim'] is not None:
        axA1.set_ylim(config['set_ylim'][0], config['set_ylim'][1])
    elif config['tight_layout']:
        axA1.set_xlim(minx,maxx)
        ydelta = 0.01 * (maxy-miny)
        axA1.set_ylim(miny-ydelta,maxy+ydelta)
    else:
        corners = (minx, miny), (maxx, maxy)
        axA1.update_datalim(corners)

    if config['return_calculated_values'] is not None:
        retdict = config['return_calculated_values']
        if ptype in VALID_PMOVE_TYPES:
            prekey = ptype
            retdict[prekey+'_bricks'] = brick_values
            retdict[prekey+'_dates'] = mdates.num2date(new_dates)
            retdict[prekey+'_size'] = size
            if config['volume']:
                retdict[prekey+'_volumes'] = volumes
        if mavgs is not None:
            for i in range(0, len(mavgs)):
                retdict['mav' + str(mavgs[i])] = mavprices
        retdict['minx'] = minx
        retdict['maxx'] = maxx
        retdict['miny'] = miny
        retdict['maxy'] = maxy

    # Note: these are NOT mutually exclusive, so the order of this
    #       if/elif is important: VALID_PMOVE_TYPES must be first.
    if ptype in VALID_PMOVE_TYPES:
        dtix = pd.DatetimeIndex([dt for dt in mdates.num2date(new_dates)])
    elif not config['show_nontrading']:
        dtix = data.index
    else:
        dtix = None

    line_collections = []
    line_collections.append(_construct_aline_collections(config['alines'], dtix))
    line_collections.append(_construct_hline_collections(config['hlines'], minx, maxx))
    line_collections.append(_construct_vline_collections(config['vlines'], dtix, miny, maxy))
    tlines = config['tlines']
    if isinstance(tlines,(list,tuple)) and all([isinstance(item,dict) for item in tlines]):
        pass
    else:
        tlines = [tlines,]
    for tline_item in tlines:
        line_collections.append(_construct_tline_collections(tline_item, dtix, dates, opens, highs, lows, closes))
     
    for collection in line_collections:
        if collection is not None:
            axA1.add_collection(collection)

    datalen = len(xdates)
    if config['volume']:
        vup,vdown = style['marketcolors']['volume'].values()
        #-- print('vup,vdown=',vup,vdown)
        vcolors = _updown_colors(vup, vdown, opens, closes, use_prev_close=style['marketcolors']['vcdopcod'])
        #-- print('len(vcolors),len(opens),len(closes)=',len(vcolors),len(opens),len(closes))
        #-- print('vcolors=',vcolors)

        w  = config['_width_config']['volume_width']
        lw = config['_width_config']['volume_linewidth']

        adjc =  _adjust_color_brightness(vcolors,0.90)
        volumeAxes.bar(xdates,volumes,width=w,linewidth=lw,color=vcolors,ec=adjc)
        miny = 0.3 * np.nanmin(volumes)
        maxy = 1.1 * np.nanmax(volumes)
        volumeAxes.set_ylim( miny, maxy )

    xrotation = config['xrotation']
    _set_ticks_on_bottom_panel_only(panels,formatter,rotation=xrotation)

    addplot = config['addplot']
    if addplot is not None and ptype not in VALID_PMOVE_TYPES:
        # Calculate the Order of Magnitude Range ('mag')
        # If addplot['secondary_y'] == 'auto', then: If the addplot['data']
        # is out of the Order of Magnitude Range, then use secondary_y.
        # Calculate omrange for Main panel, and for Lower (volume) panel:
        lo = math.log(max(math.fabs(np.nanmin(lows)),1e-7),10) - 0.5
        hi = math.log(max(math.fabs(np.nanmax(highs)),1e-7),10) + 0.5

        panels['mag'] = [None]*len(panels)  # create 'mag' column

        panels.at[config['main_panel'],'mag'] = {'lo':lo,'hi':hi} # update main panel magnitude range

        if config['volume']:
            lo = math.log(max(math.fabs(np.nanmin(volumes)),1e-7),10) - 0.5
            hi = math.log(max(math.fabs(np.nanmax(volumes)),1e-7),10) + 0.5
            panels.at[config['volume_panel'],'mag'] = {'lo':lo,'hi':hi}

        if isinstance(addplot,dict):
            addplot = [addplot,]   # make list of dict to be consistent

        elif not _list_of_dict(addplot):
            raise TypeError('addplot must be `dict`, or `list of dict`, NOT '+str(type(addplot)))

        for apdict in addplot:
            apdata = apdict['data']
            if isinstance(apdata,list) and not isinstance(apdata[0],(float,int)):
                raise TypeError('apdata is list but NOT of float or int')
            if isinstance(apdata,pd.DataFrame): 
                havedf = True
            else:
                havedf = False      # must be a single series or array
                apdata = [apdata,]  # make it iterable

            for column in apdata:
                if havedf:
                    ydata = apdata.loc[:,column]
                else:
                    ydata = column
                yd = [y for y in ydata if not math.isnan(y)]
                ymhi = math.log(max(math.fabs(np.nanmax(yd)),1e-7),10)
                ymlo = math.log(max(math.fabs(np.nanmin(yd)),1e-7),10)
                secondary_y = False
                panid = apdict['panel']
                if   panid == 'main' : panid = 0  # for backwards compatibility
                elif panid == 'lower': panid = 1  # for backwards compatibility
                if apdict['secondary_y'] == 'auto':
                    # If mag(nitude) for this panel is not yet set, then set it
                    # here, as this is the first ydata to be plotted on this panel:
                    # i.e. consider this to be the 'primary' axis for this panel.
                    p = panid,'mag'
                    if panels.at[p] is None:
                        panels.at[p] = {'lo':ymlo,'hi':ymhi}
                    elif ymlo < panels.at[p]['lo'] or ymhi > panels.at[p]['hi']:
                        secondary_y = True
                    #if secondary_y:
                    #    print('auto says USE secondary_y ... for panel',panid)
                    #else:
                    #    print('auto says do NOT use secondary_y ... for panel',panid)
                else:
                    secondary_y = apdict['secondary_y']
                    #print("apdict['secondary_y'] says secondary_y is",secondary_y)

                if secondary_y:
                    ax = panels.at[panid,'axes'][1] 
                    panels.at[panid,'used2nd'] = True
                else: 
                    ax = panels.at[panid,'axes'][0]

                if (apdict["ylabel"] is not None):
                    ax.set_ylabel(apdict["ylabel"])

                aptype = apdict['type']
                if aptype == 'scatter':
                    size  = apdict['markersize']
                    mark  = apdict['marker']
                    color = apdict['color']
                    if isinstance(mark,(list,tuple,np.ndarray)):
                        _mscatter(xdates, ydata, ax=ax, m=mark, s=size, color=color)
                    else:
                        ax.scatter(xdates, ydata, s=size, marker=mark, color=color)
                elif aptype == 'bar':
                    width  = apdict['width']
                    bottom = apdict['bottom']
                    color  = apdict['color']
                    alpha  = apdict['alpha']
                    ax.bar(xdates, ydata, width=width, bottom=bottom, color=color, alpha=alpha)
                elif aptype == 'line':
                    ls    = apdict['linestyle']
                    color = apdict['color']
                    ax.plot(xdates, ydata, linestyle=ls, color=color)
                #elif aptype == 'ohlc' or aptype == 'candle':
                # This won't work as is, because here we are looping through one column at a time
                # and mpf_collections needs ohlc columns:
                #    collections =_construct_mpf_collections(aptype,dates,xdates,opens,highs,lows,closes,volumes,config,style)
                #    if len(collections) == 1: collections = [collections]
                #    for collection in collections:
                #        ax.add_collection(collection)
                else:
                    raise ValueError('addplot type "'+str(aptype)+'" NOT yet supported.')


    if config['fill_between'] is not None:
        fb    = config['fill_between']
        panid = config['main_panel']
        if isinstance(fb,dict):
            if 'x' in fb:
                raise ValueError('fill_between dict may not contain `x`')
            if 'panel' in fb:
                panid = fb['panel']
                del fb['panel']
        else:
            fb = dict(y1=fb)
        fb['x'] = xdates
        ax = panels.at[panid,'axes'][0]
        ax.fill_between(**fb)
            
    if config['set_ylim_panelB'] is not None:
        miny = config['set_ylim_panelB'][0]
        maxy = config['set_ylim_panelB'][1]
        panels.at[1,'axes'][0].set_ylim( miny, maxy )

    # put the twinx() on the "other" side:
    if style['y_on_right']:
        for ax in panels['axes'].values:
            ax[0].yaxis.set_label_position('right')
            ax[0].yaxis.tick_right()
            ax[1].yaxis.set_label_position('left')
            ax[1].yaxis.tick_left()
    else:
        for ax in panels['axes'].values:
            ax[0].yaxis.set_label_position('left')
            ax[0].yaxis.tick_left()
            ax[1].yaxis.set_label_position('right')
            ax[1].yaxis.tick_right()

    # TODO: ================================================================
    # TODO:  Investigate:
    # TODO:  ===========
    # TODO:  It appears to me that there may be some or significant overlap
    # TODO:  between what the following functions actually do:
    # TODO:  At the very least, all four of them appear to communicate 
    # TODO:  to matplotlib that the xaxis should be treated as dates:
    # TODO:   ->  'ax.autoscale_view()'
    # TODO:   ->  'ax.xaxis_dates()'
    # TODO:   ->  'plt.autofmt_xdates()'
    # TODO:   ->  'fig.autofmt_xdate()'
    # TODO: ================================================================
    

    #if config['autofmt_xdate']:
        #print('CALLING fig.autofmt_xdate()')
        #fig.autofmt_xdate()

    axA1.autoscale_view()  # Is this really necessary??

    axA1.set_ylabel(config['ylabel'])

    if config['volume']:
        volumeAxes.figure.canvas.draw()  # This is needed to calculate offset
        offset = volumeAxes.yaxis.get_major_formatter().get_offset()
        volumeAxes.yaxis.offsetText.set_visible(False)
        if len(offset) > 0:
            offset = (' x '+offset)
        if config['ylabel_lower'] is None:
            vol_label = 'Volume'+offset
        else:
            if len(offset) > 0:
                offset = '\n'+offset
            vol_label = config['ylabel_lower'] + offset
        volumeAxes.set_ylabel(vol_label)

    if config['title'] is not None:
        if config['tight_layout']:
            # IMPORTANT: 0.89 is based on the top of the top panel
            #            being at 0.18+0.7 = 0.88.  See _panels.py
            # If the value changes there, then it needs to change here.
            fig.suptitle(config['title'],size='x-large',weight='semibold', va='bottom', y=0.89)
        else:
            fig.suptitle(config['title'],size='x-large',weight='semibold', va='center')

    for panid,row in panels.iterrows():
        if not row['used2nd']:
            row['axes'][1].set_visible(False)

    # Should we create a new kwarg to return a flattened axes list
    # versus a list of tuples of primary and secondary axes?
    # For now, for backwards compatibility, we flatten axes list:
    axlist = [ax for axes in panels['axes'] for ax in axes]

    if config['axisoff']:
        for ax in axlist:
            ax.set_xlim(xdates[0],xdates[-1])
            ax.set_axis_off()

    if config['savefig'] is not None:
        save = config['savefig']
        if isinstance(save,dict):
            # Expand to fill chart if axisoff
            if config['axisoff'] and 'bbox_inches' not in save:
                plt.savefig(**save,bbox_inches='tight')
            else:
                plt.savefig(**save)
        else:
            if config['axisoff']:
                plt.savefig(save,bbox_inches='tight')
            else:
                plt.savefig(save)
        if config['closefig']: # True or 'auto'
            plt.close(fig)
    elif not config['returnfig']:
        plt.show(block=config['block']) # https://stackoverflow.com/a/13361748/1639359 
        if config['closefig'] == True or (config['block'] and config['closefig']):
            plt.close(fig)
    
    if config['returnfig']:
        if config['closefig'] == True: plt.close(fig)
        return (fig, axlist)

    # rcp   = copy.deepcopy(plt.rcParams)
    # rcpdf = rcParams_to_df(rcp)
    # print('type(rcpdf)=',type(rcpdf))
    # print('rcpdfhead(3)=',rcpdf.head(3))
    # return # rcpdf


def _valid_addplot_kwargs():

    valid_linestyles = ('-','solid','--','dashed','-.','dashdot','.','dotted',None,' ','')
    #valid_types = ('line','scatter','bar','ohlc','candle')
    valid_types = ('line','scatter','bar')

    vkwargs = {
        'scatter'     : { 'Default'     : False,
                          'Validator'   : lambda value: isinstance(value,bool) },

        'type'        : { 'Default'     : 'line',
                          'Validator'   : lambda value: value in valid_types },

        'panel'       : { 'Default'     : 0, 
                          'Validator'   : lambda value: _valid_panel_id(value) },

        'marker'      : { 'Default'     : 'o',
                          'Validator'   : lambda value: _bypass_kwarg_validation(value)  },

        'markersize'  : { 'Default'     : 18,
                          'Validator'   : lambda value: isinstance(value,(int,float)) },

        'color'       : { 'Default'     : None,
                          'Validator'   : lambda value: mcolors.is_color_like(value) or
                                         (isinstance(value,(list,tuple,np.ndarray)) and all([mcolors.is_color_like(v) for v in value])) },

        'linestyle'   : { 'Default'     : None,
                          'Validator'   : lambda value: value in valid_linestyles },

        'width'       : { 'Default'     : 0.8,
                          'Validator'   : lambda value: isinstance(value,(int,float)) or
                                                        all([isinstance(v,(int,float)) for v in value]) },

        'bottom'      : { 'Default'     : 0,
                          'Validator'   : lambda value: isinstance(value,(int,float)) or
                                                        all([isinstance(v,(int,float)) for v in value]) },
        'alpha'       : { 'Default'     : 1,
                          'Validator'   : lambda value: isinstance(value,(int,float)) or
                                                        all([isinstance(v,(int,float)) for v in value]) },

        'secondary_y' : { 'Default'     : 'auto',
                          'Validator'   : lambda value: isinstance(value,bool) or value == 'auto' },
        
        'ylabel'      : { 'Default'     : None,
                          'Validator'   : lambda value: isinstance(value,str) },
    }

    _validate_vkwargs_dict(vkwargs)

    return vkwargs


def make_addplot(data, **kwargs):
    '''
    Take data (pd.Series, pd.DataFrame, np.ndarray of floats, list of floats), and
    kwargs (see valid_addplot_kwargs_table) and construct a correctly structured dict
    to be passed into plot() using kwarg `addplot`.  
    NOTE WELL: len(data) here must match the len(data) passed into plot()
    '''
    if not isinstance(data, (pd.Series, pd.DataFrame, np.ndarray, list)):
        raise TypeError('Wrong type for data, in make_addplot()')

    config = _process_kwargs(kwargs, _valid_addplot_kwargs())

    # kwarg `type` replaces kwarg `scatter`
    if config['scatter'] == True and config['type'] == 'line':
        config['type'] = 'scatter'

    return dict( data=data, **config)
