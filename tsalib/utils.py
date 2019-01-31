from tsalib.ts import TS, DimVar, dummy_dvar, TupleSeq
from sympy import sympify, Symbol
import re

def _sexpr_to_ts (e, dummy_idx=-1, strict=False):
    '''
    A single string expression (sexpr) to Tensor Shape expressions (ts)
    Converts shorthand dummy/empty placeholders to dummy TSs
    '''
    if isinstance(e, TS):  
        t = e
    else: 
        assert isinstance(e, str)
        if e == '' or e =='_':  
            t = dummy_dvar(dummy_idx)
            dummy_idx += 1
        elif e == '^':
            #TODO: better way to handle '^' ?
            t = TS(Symbol(e))
        else: 
            #TODO: strict: check if all dim vars in e are previously declared?
            t = TS(sympify(e))

    return t, dummy_idx

def _sexprs_to_ts(exprs, strict=False):
    '''
    String expressions (sexprs) to Tensor Shape expressions (ts)
    Converts shorthand dummy/empty placeholders to dummy TSs
    Returns a tuple of TSs
    '''
    dummy_idx = 0
    res = []
    for e in exprs:
        t, dummy_idx = _sexpr_to_ts(e, dummy_idx, strict)
        res.append(t)

    #print (exprs, res)
    return tuple(res)


seq_re = r'\((.+)\)\*'

def _to_str_list(ss: str):
    # 'btd' -> ['b','t','d']

    #remove all whitespace characters
    ss = re.sub(r'\s+', '', ss)

    #check if shape corresponds to a sequence        
    is_seq = False
    m = re.search(seq_re, ss)
    if m is not None:  # ss = '(b,t,d)*'
        ss = m.groups()[0]  # ss = 'b,t,d'
        #print (f'groups: {m.groups()}') 
        is_seq = True

    if ',' in ss: exprs = ss.strip().split(',') #'b,t,d*2' -> ['b', 't', 'd*2']
    else: exprs = list(ss)  

    return exprs, is_seq 

def _to_tuple (ss):
    '''
    :ss is shape string, e.g., 'btd' or 'b,t,d*2' or '(btd)*'
    :returns the shape representation in tuple/TupleSeq form
    '''
    if isinstance(ss, (list, tuple)):
        for s in ss: assert isinstance(s, (TS,int))
        return tuple(ss)
    elif isinstance(ss, TupleSeq):
        return ss
    elif isinstance(ss, str):
        exprs, is_seq = _to_str_list(ss)  # 'btd' -> 'b', 't', 'd'
        exprs = _sexprs_to_ts(exprs)
        for e in exprs:
            assert isinstance(e, TS)

        exprs = tuple(exprs)

        if is_seq:
            exprs = TupleSeq(exprs)

        return exprs

    else:
        raise ValueError('Unknown type of ss')

def check_int_tuple(s):
    #print(f'int tuple? {s}')
    for d in s:
        try: d = int(d)
        except:
            raise ValueError(f'Unable to resolve expression {d}')
def is_int_tuple(s):
    ret = all([isinstance(x, int) for x in s])
    return ret

def resolve_to_int_tuple(s):
    '''
    resolve non-int elements by casting to int or looking up their DimVar values
    '''
    res = []
    for d in s:
        try: 
            d = int(d)
            res.append(d)
        except:
            if isinstance(d, TS):
                e = d.exp
            elif isinstance(d, Symbol):
                e = d
            else:
                raise ValueError(f'Unknown item {d}: {type(d)}')
            
            r = DimVar.eval(e)
            #print('r is ', r)
            try: 
                r = int(r)
                res.append(r)
            except:
                raise ValueError(f'Unable to resolve {d}')

    return tuple(res)


def to_int_tuple(s):
    return tuple([int(d) for d in s])

def tsn_to_shape (tsn):
    '''
    tsn: 'b,t,h*d'
    Lookup each shorthand in cache. 
    returns: (B, T, H*D)
    '''
    assert isinstance(tsn, str)
    return _to_tuple(tsn)

def get(x, dv_dict):
    '''
    Index using dimension shorthands
    
    x: arbitrary tensor (can be indexed in numpy notation : x[:,0,:])
    dv_dict: {'b': 0, 'c': 5} 
    x_tsa: 'b,c,d'
    '''

    assert isinstance(tuple), 'The first argument should be a tuple of (vector, shape)'
    xv, xs = x
    shape, is_seq = _to_str_list(xs)
    if not is_seq:
        raise NotImplementedError(f"get from shape {xs} not implemented")

    colon = slice(None)
    slice_tuple = []
    for sh in shape:
        if sh in dv_dict:
            slice_tuple.append(dv_dict[sh])
        else:
            slice_tuple.append(colon)

    y = x[slice_tuple]
    return y