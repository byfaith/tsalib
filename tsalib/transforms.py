from .ts import dim_var, DimExpr, dummy_dvar, TupleSeq
from sympy import sympify, Integer
from .tsn import _sexprs_to_ts, tsn_to_str_list, tsn_to_tuple, check_int_tuple, resolve_to_int_tuple



def _view_transform (src, to, in_shape):
    '''
    View Transform
    src, to: Union[str, Tuple]
    :src is the current view of the tensor
    :to is the target view, may contain expressions over named dim variables
    :in_shape is the shape (list/tuple) of the source tensor 
    :returns the new size of the tensor after view transformation (backend independent)
    '''
    check_int_tuple(in_shape)

    src = tsn_to_tuple(src)
    if (len(src) != len(in_shape)):
        print (f'{src}, {in_shape}')
        raise ValueError("Source DimExpr does not match input tensor's shape")
    to = tsn_to_tuple(to)
    #print (src, to)
    assert isinstance(in_shape, (list, tuple))
    assert isinstance(src, tuple)
    assert isinstance(to, tuple)

    #sub_map = [(d.e, Symbol(f'{i}')) for i, d in enumerate(src)]
    sub_map = [(d.exp, in_shape[i]) for i, d in enumerate(src)]
    out_shape = tuple([t.exp.subs(sub_map) if isinstance(t, DimExpr) else int(t) for t in to])

    out_shape = resolve_to_int_tuple(out_shape)
    return out_shape

def view_transform (tfm, in_shape):
    '''
    View transform
    :tfm:str is the shorthand representation of the transform ('btd -> b,t*2,d//2')
    '''
    l, r = tfm.split('->')
    return _view_transform(l.strip(), r.strip(), in_shape)


def _permute_transform(src, to):
    '''
    Permute Transform
    src, to: Union[str, Tuple]

    :src is the current dimension arrangement, list of named dim variables
    :to is the target dimension arragement, list of named dim variables
    :returns the index tuple for the permutation (backend independent)
    '''
    src = tsn_to_tuple(src)
    to = tsn_to_tuple(to)
    assert isinstance(src, tuple)
    assert isinstance(to, tuple)

    assert len(src) == len(to), "Source and Target shapes for permutation are not same"

    sub_map = [(d.exp, i) for i, d in enumerate(src)]
    perm_indices = tuple([t.exp.subs(sub_map) for t in to])
    perm_indices = resolve_to_int_tuple(perm_indices)

    return perm_indices


def permute_transform (tfm):
    '''
    Permute transform
    :tfm: str
    :tfm is the shorthand representation of the transform (',t,d -> ,d,t')
    '''
    l, r = tfm.split('->')
    return _permute_transform(l.strip(), r.strip())

def _expansions_as_dict(expansions):
    if isinstance(expansions, list): #[(T, T*5), (D, D*4)]
        res = expansions
    else:
        assert isinstance(expansions, str) #'k->k*5,t->t*10'
        expansions = expansions.strip().split(',')
        res = []
        for ex in expansions:
            t = _sexprs_to_ts(ex.strip().split('->'))
            #print(t)
            res.append(t)
            #print (res)

    exp_map = {l: r for (l, r) in res}
    return exp_map


def expand_transform (src, expansions, in_shape):
    '''
    :src        (B, T, D) = (10, 20, 300)
    :expansions [(T, T*5), (D, D*4)]
    :returns the expansion shape tuple
    '''
    src = tsn_to_tuple(src)
    exp_map = _expansions_as_dict(expansions)
    #exp_map = {_sexpr_to_ts(s)[0]: _sexpr_to_ts(t)[0] for (s, t) in (expansions)}
    sub_map = [(d.exp, in_shape[i]) for i, d in enumerate(src)] # (B, 10), (T, 20), (D, 300)

    #print (expansions, exp_map)

    res = []
    for k in src:
        if k not in exp_map: res.append(-1) #keep dim shape same
        else:
            v = exp_map[k]
            assert isinstance(v, DimExpr)
            res.append(v.exp.subs(sub_map)) #(T*5) -> 100, (D*4) -> 1200

    res = tuple(res)
    res = resolve_to_int_tuple(res)
    return res



def _join_transform (tlist, src, to):
    '''
    src: Union[str, TupleSeq]
    to: Union[str, tuple]
    src: (b,c,d)* , to: '^, b, c, d'    OR
    src: (b,c,d)* , to: 'b, 3*c, d'

    returns the dims shorthand for joining (backend independent)

    '''
    lhs = tsn_to_tuple(src) #TupleSeq(B, C, D)
    rhs = tsn_to_tuple(to) 

    assert isinstance(lhs, TupleSeq)
    assert isinstance(rhs, tuple)

    lhs = lhs.item() # (b, c, d)
    int1 = Integer(1) # substitute all dim shorthands by '1'

    sub_map = [(d.exp, int1) for d in lhs]
    dims = tuple([t.exp.subs(sub_map) for t in rhs]) # (^, 1, 1, 1)


    if len(rhs) == len(lhs): #concat, join by '*'
        #join_dims = (1,3*1,1)
        dims = ','.join(map(lambda x: '' if x == int1 else '*', dims))
        #dims = ',*,'
    elif len(rhs) == (len(lhs) + 1): #stack, join by '^'
        dims = ','.join(map(lambda x: '' if x == int1 else '^', dims))
        #dims = '^,,,'
    else:
        raise ValueError(f'Unable to join from {src} to {to}')

    return dims


def join_transform (tlist, tfm):
    '''
    Join transform (backend independent)
    :tlist: List[tensor]
    :tfm:str represents the transform "(b,c,d)* -> ^,b,c,d"
    returns the dims in TSN for joining 

    '''
    l, r = tfm.split('->')
    return _join_transform(tlist, l.strip(), r.strip())


def align_transform (src, to):
    '''
    src: 'd,d'
    to: '6, d, t, d'
    return: '^,,^,' [expansion shorthand for src]
    '''

    lhs = tsn_to_tuple(src) #TupleSeq(B, C, D)
    rhs = tsn_to_tuple(to) 

    assert isinstance(lhs, tuple)
    assert isinstance(rhs, tuple)

    lhs_pos, rhs_pos = 0, 0
    res = []
    for rhs_pos, d in enumerate(rhs):
        if lhs[lhs_pos] == d: 
            #print ('match', d, lhs[lhs_pos])
            res.append('')
            lhs_pos += 1
        else:
            res.append('^')

    #print (lhs_pos, res)

    if lhs_pos != len(lhs):
        print (f'Unable to align {src} to {to}: {src} not a subsequence of {to}')
        raise ValueError

    return ','.join(res)


def expand(x, tfm):
    '''
    x: (backend) tensor, e.g., shape 'd,d'
    tfm: expand tsn: '^,,^,'
    returns tensor of shape '1,d,1,d'
    '''

    colon = slice(None)
    expand_tup = tuple(None if c == '^' else colon for c in tfm.split(','))
    return x[expand_tup]


def alignto(x, y):
    '''
    Align tensor x's shape to y's shape.
    Assume x's shape is a subsequence of y's shape
    Assume tensors x and y support numpy's "None, :"" indexing notation
    x: (tensor_var, x_shape)
    y: (tensor_var, y_shape)
    '''

    assert isinstance(x, tuple) and isinstance(y, tuple), 'Arguments are of form (tensor_var, shothand shape)'

    xt, xs = x
    yt, ys = y

    expand_tfm = align_transform(xs, ys)
    return expand(xt, expand_tfm)











