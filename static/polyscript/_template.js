const { assign: assign$1 } = Object;

const STORAGE = 'entries';
const READONLY = 'readonly';
const READWRITE = 'readwrite';

/**
 * @typedef {Object} IDBMapOptions
 * @prop {'strict' | 'relaxed' | 'default'} [durability]
 * @prop {string} [prefix]
 */

/** @typedef {[IDBValidKey, unknown]} IDBMapEntry */

/** @type {IDBMapOptions} */
const defaultOptions = { durability: 'default', prefix: 'IDBMap' };

/**
 * @template T
 * @param {{ target: IDBRequest<T> }} event
 * @returns {T}
 */
const result$1 = ({ target: { result } }) => result;

class IDBMap extends EventTarget {
  // Privates
  /** @type {Promise<IDBDatabase>} */ #db;
  /** @type {IDBMapOptions} */ #options;
  /** @type {string} */ #prefix;

  /**
   * @template T
   * @param {(store: IDBObjectStore) => IDBRequest<T>} what
   * @param {'readonly' | 'readwrite'} how
   * @returns {Promise<T>}
   */
  async #transaction(what, how) {
    const db = await this.#db;
    const t = db.transaction(STORAGE, how, this.#options);
    return new Promise((onsuccess, onerror) => assign$1(
      what(t.objectStore(STORAGE)),
      {
        onsuccess,
        onerror,
      }
    ));
  }

  /**
   * @param {string} name
   * @param {IDBMapOptions} options
   */
  constructor(
    name,
    {
      durability = defaultOptions.durability,
      prefix = defaultOptions.prefix,
    } = defaultOptions
  ) {
    super();
    this.#prefix = prefix;
    this.#options = { durability };
    this.#db = new Promise((resolve, reject) => {
      assign$1(
        indexedDB.open(`${this.#prefix}/${name}`),
        {
          onupgradeneeded({ target: { result, transaction } }) {
            if (!result.objectStoreNames.length)
              result.createObjectStore(STORAGE);
            transaction.oncomplete = () => resolve(result);
          },
          onsuccess(event) {
            resolve(result$1(event));
          },
          onerror(event) {
            reject(event);
            this.dispatchEvent(event);
          },
        },
      );
    }).then(result => {
      const boundDispatch = this.dispatchEvent.bind(this);
      for (const key in result) {
        if (key.startsWith('on'))
          result[key] = boundDispatch;
      }
      return result;
    });
  }

  // EventTarget Forwards
  /**
   * @param {Event} event
   * @returns 
   */
  dispatchEvent(event) {
    const { type, message, isTrusted } = event;
    return super.dispatchEvent(
      // avoid re-dispatching of the same event
      isTrusted ?
        assign$1(new Event(type), { message }) :
        event
    );
  }

  // IDBDatabase Forwards
  async close() {
    (await this.#db).close();
  }

  // Map async API
  get size() {
    return this.#transaction(
      store => store.count(),
      READONLY,
    ).then(result$1);
  }

  async clear() {
    await this.#transaction(
      store => store.clear(),
      READWRITE,
    );
  }

  /**
   * @param {IDBValidKey} key
   */
  async delete(key) {
    await this.#transaction(
      store => store.delete(key),
      READWRITE,
    );
  }

  /**
   * @returns {Promise<IDBMapEntry[]>}
   */
  async entries() {
    const keys = await this.keys();
    return Promise.all(keys.map(key => this.get(key).then(value => [key, value])));
  }

  /**
   * @param {(unknown, IDBValidKey, IDBMap) => void} callback
   * @param {unknown} [context]
   */
  async forEach(callback, context = this) {
    for (const [key, value] of await this.entries())
      await callback.call(context, value, key, this);
  }

  /**
   * @param {IDBValidKey} key
   * @returns {Promise<unknown | undefined>}
   */
  async get(key) {
    const value = await this.#transaction(
      store => store.get(key),
      READONLY,
    ).then(result$1);
    return value;
  }

  /**
   * @param {IDBValidKey} key
   */
  async has(key) {
    const k = await this.#transaction(
      store => store.getKey(key),
      READONLY,
    ).then(result$1);
    return k !== void 0;
  }

  async keys() {
    const keys = await this.#transaction(
      store => store.getAllKeys(),
      READONLY,
    ).then(result$1);
    return keys;
  }

  /**
   * @param {IDBValidKey} key
   * @param {unknown} value
   */
  async set(key, value) {
    await this.#transaction(
      store => store.put(value, key),
      READWRITE,
    );
    return this;
  }

  async values() {
    const keys = await this.keys();
    return Promise.all(keys.map(key => this.get(key)));
  }

  get [Symbol.toStringTag]() {
    return this.#prefix;
  }
}

class IDBMapSync extends Map {
  #map;
  #queue;
  constructor(...args) {
    super();
    this.#map = new IDBMap(...args);
    this.#queue = this.#map.entries().then(entries => {
      for (const [key, value] of entries)
        super.set(key, value);
    });
  }
  async close() {
    await this.#queue;
    await this.#map.close();
  }
  async sync() {
    await this.#queue;
  }
  clear() {
    this.#queue = this.#queue.then(() => this.#map.clear());
    return super.clear();
  }
  delete(key) {
    this.#queue = this.#queue.then(() => this.#map.delete(key));
    return super.delete(key);
  }
  set(key, value) {
    this.#queue = this.#queue.then(() => this.#map.set(key, value));
    return super.set(key, value);
  }
}

let e$1="coincident-";try{new SharedArrayBuffer(4,{maxByteLength:8}),e$1+=crypto.randomUUID();}catch(r){e$1+=Math.random().toString(36).substring(2);}const{fromCharCode:r$2}=String,{min:t$1}=Math;var n$1=0,s$1=1,c$1=2,o$1=3,a$1=4,u$1=5,l$1=6,i$1=7,f$1=8,y=9,h$1=10,w=11,d$1=12,p$1=13,g=14,b$1=15,m=16,S=17;const{defineProperty:v}=Object,x=e=>{switch(e[U++]){case s$1:{const r=e[U++],t=[];e[U-2]=t;for(let n=0;n<r;n++)t[n]=x(e);return t}case c$1:{const r=e[U++],t={};e[U-2]=t;for(let n=0;n<r;n++)t[x(e)]=x(e);return t}case a$1:{const r=e[U++];return e[U-2]=r,r}case o$1:return e[U++];case u$1:return  true;case l$1:return  false;case i$1:return null;case p$1:return;case d$1:return BigInt(e[U++]);case f$1:{const r=e[U++],t=e[U++],n=[r];t&&n.push({maxByteLength:t});const s=new ArrayBuffer(...n);e[U-3]=s;const c=new Uint8Array(s,0,r);for(let t=0;t<r;t++)c[t]=e[U++];return s}case y:{const r=e[U++],t=e[U++],n=e[U++],s=U-4,c=[x(e),t];n&&c.push(n);const o=new globalThis[r](...c);return e[s]=o,o}case w:{const r=new Date(e[U++]);return e[U-2]=r,r}case g:{const r=e[U++],t=new Map;e[U-2]=t;for(let n=0;n<r;n++){const r=x(e),n=x(e);void 0!==r&&t.set(r,n);}return t}case b$1:{const r=e[U++],t=new Set;e[U-2]=t;for(let n=0;n<r;n++){const r=x(e);void 0!==r&&t.add(r);}return t}case m:{const r=e[U++],t=e[U++],n=new RegExp(r,t);return e[U-3]=n,n}case S:{const r=globalThis[e[U++]]||Error,t=e[U++],n=e[U++],s=new r(t,{cause:e[U++]});return e[U-5]=v(s,"stack",{value:n}),s}case h$1:return (r=e[U++]).startsWith("Symbol.")?Symbol[r.slice(r.indexOf(".")+1)]:Symbol.for(r);case n$1:return e[e[U++]];default:throw new TypeError(`Unknown type: ${e[U-1]}`)}var r;},{parse:B}=JSON;let U=0;const A=e=>(U=0,e.length?x(e):void 0),O=e=>A(B(e)),E=(e=>({byteOffset:n=0}={})=>(s,c)=>{const o=new Uint16Array(c,n,s);let a="",u=0;for(;u<s;){const e=t$1(u+32767,s);a+=r$2.apply(null,o.subarray(u,e)),u=e;}return e(a)})(O);

// ⚠️ AUTOMATICALLY GENERATED - DO NOT CHANGE
const CHANNEL = '940beb37';
const MAIN = '=' + CHANNEL;
const WORKER = '-' + CHANNEL;

const {
  create: create$3,
} = Object;

/* c8 ignore start */
let ID = 'coincident-', native$1 = true;
try {
  new SharedArrayBuffer(4, { maxByteLength: 8 });
  ID += crypto.randomUUID();
}
catch (_) {
  native$1 = false;
  ID += Math.random().toString(36).substring(2);
}
/* c8 ignore end */

const byteOffset = 2 * Int32Array.BYTES_PER_ELEMENT;
const minByteLength = 0x7FFF; // throws at 0xFFFF via .apply(...)
const maxByteLength = 0x1000000;

const defaults = {
  // ⚠️ mandatory: first int32 to notify, second one to store the written length
  byteOffset,
  // ⚠️ mandatory: to encode *into* a SharedArrayBuffer
  useUTF16: true,
  // ⚠️ mandatory: to satisfy circular/cyclic data
  circular: true,
};

const result = async (data, proxied, transform) => {
  try {
    const result = await proxied[data[1]].apply(null, data[2]);
    data[1] = transform ? transform(result) : result;
    data[2] = null;
  }
  catch (error) { data[2] = error; }
};

const set$1 = (proxied, name, callback) => {
  const ok = name !== 'then';
  if (ok) proxied[name] = callback;
  return ok;
};

/** @param {Event} event */
const stop = event => {
  event.stopImmediatePropagation();
  event.preventDefault();
};

const { fromCharCode } = String;
const { min } = Math;

var createDecoder = decode => ({ byteOffset = 0 } = {}) => (length, buffer) => {
  const ui16a = new Uint16Array(buffer, byteOffset, length);
  let json = '', i = 0;
  while (i < length) {
    const next = min(i + minByteLength, length);
    json += fromCharCode.apply(null, ui16a.subarray(i, next));
    i = next;
  }
  return decode(json);
};

const { parse: parse$2 } = JSON;

const decoder$2 = createDecoder(parse$2);

const ARRAY     = 'array';
const BIGINT    = 'bigint';
const BOOLEAN   = 'boolean';
const FUNCTION  = 'function';
const NULL      = 'null';
const NUMBER    = 'number';
const OBJECT    = 'object';
const STRING    = 'string';
const SYMBOL    = 'symbol';
const UNDEFINED = 'undefined';

// this literal allows mapping right away
// string types into numeric values so that
// the transported and transformed arrays
// would use less bytes to satisfy te same
// contract while exchanging information.
// basically this is an home-made ENUM like
// object literal ... that's it.
// TBD: should this be part of js-proxy? it feels
//      to me like it would rather belong in there.
var numeric = {
  [ARRAY]: 0,
  [BIGINT]: 1,
  [BOOLEAN]: 2,
  [FUNCTION]: 3,
  [NULL]: 4,
  [NUMBER]: 5,
  [OBJECT]: 6,
  [STRING]: 7,
  [SYMBOL]: 8,
  [UNDEFINED]: 9,
  view: 10,
};

const { parse: parse$1 } = JSON;

const decode = json => {
  const result = parse$1(json);
  switch (result[0]) {
    case numeric.view: {
      const [name, buffer] = result[1];
      const ui8a = new Uint8Array(buffer);
      result[1] = new globalThis[name](ui8a.buffer);
      break;
    }
    case numeric[UNDEFINED]: {
      result[1] = void 0;
      break;
    }
    case numeric[BIGINT]: {
      result[1] = BigInt(result[1]);
      break;
    }
  }
  return result;
};

const decoder$1 = createDecoder(decode);

//@ts-check

/**
 * @template T
 * @typedef {{promise: Promise<T>, resolve: (value: T) => void, reject: (reason?: any) => void}} Resolvers
 */

//@ts-ignore
const withResolvers = Promise.withResolvers;

/**
 * @template T
 * @type {() => Resolvers<T>}
 */
var withResolvers$1 = withResolvers.bind(Promise);

//@ts-check


/**
 * @template V
 * @callback Resolve
 * @param {V?} [value]
 * @returns {void}
 */

/**
 * @callback Reject
 * @param {any?} [error]
 * @returns {void}
 */

/**
 * @template V
 * @typedef {object} Resolvers
 * @prop {Promise<V>} promise
 * @prop {Resolve<V>} resolve
 * @prop {Reject} reject
 */

/**
 * @template K,V
 * @typedef {() => [K, Promise<V>]} Next
 */

/**
 * @template K,V
 * @callback Resolver
 * @param {K} uid
 * @param {V?} [value]
 * @param {any?} [error]
 */

/**
 * @template K,V
 * @typedef {[Next<K,V>, Resolver<K,V>]} NextResolver
 */

/**
 * @template K,V
 * @param {(id: number) => K} [as]
 * @returns
 */
var nextResolver = (as = (id => /** @type {K} */(id))) => {
  /** @type {Map<K,Resolvers<V>>} */
  const map = new Map;
  let id = 0;
  return /** @type {NextResolver<K,V>} */([
    /** @type {Next<K,V>} */
    () => {
      let uid;
      do { uid = as(id++); }
      while (map.has(uid));
      const wr = /** @type {Resolvers<V>} */(/** @type {unknown} */(withResolvers$1()));
      map.set(uid, wr);
      return [uid, wr.promise];
    },
    /** @type {Resolver<K,V>} */
    (uid, value, error) => {
      const wr = map.get(uid);
      map.delete(uid);
      if (error) wr?.reject(error);
      else wr?.resolve(value);
    },
  ]);
};

//@ts-check

/** @type {ArrayBuffer[]} */
const nothing = [];

/** @type {WeakSet<ArrayBuffer[]>} */
const buffers = new WeakSet;

/**
 * @param {boolean} check
 * @param {any[]} args
 * @returns
 */
const get$1 = (check, args) => {
  let transfer = nothing;
  if (check && buffers.has(args.at(-1) || nothing)) {
    transfer = args.pop();
    buffers.delete(transfer);
  }
  return transfer;
};

/**
 * @param  {...ArrayBuffer} args
 * @returns
 */
const set = (...args) => (buffers.add(args), args);

// wait for the channel before resolving
const bootstrap = Promise.withResolvers();

addEventListener(
  'message',
  event => {
    stop(event);
    bootstrap.resolve([event.data, event.ports[0]]);
  },
  { once: true }
);

var coincident$1 = async options => {
  const [ID, channel] = await bootstrap.promise;
  const WORKAROUND = native$1 && !!ID;
  const transform = options?.transform;
  const decode = (options?.decoder || decoder$2)(defaults);
  const checkTransferred = options?.transfer !== false;

  let i32a, pause, wait;
  if (native$1) {
    const sab = new SharedArrayBuffer(
      options?.minByteLength || minByteLength,
      { maxByteLength: options?.maxByteLength || maxByteLength }
    );
    i32a = new Int32Array(sab);
    ({ pause, wait } = Atomics);
    // prefer the fast path when possible
    if (pause && !WORKAROUND && !(sab instanceof ArrayBuffer)) {
      wait = (view, index) => {
        while (view[index] < 1) pause();
      };
    }
  }

  const [ next, resolve ] = nextResolver(String);
  const callbacks = new Map;
  const proxied = create$3(null);
  const proxy = new Proxy(proxied, {
    get(_, name) {
      // the curse of potentially awaiting proxies in the wild
      // requires this ugly guard around `then`
      if (name === 'then') return;
      let cb = callbacks.get(name);
      if (!cb) {
        callbacks.set(name, cb = (...args) => {
          const transfer = get$1(checkTransferred, args);
          const data = [i32a, name, transform ? args.map(transform) : args];
          // synchronous request
          if (native$1) {
            if (WORKAROUND) postMessage({ ID, data }, transfer);
            else channel.postMessage(data, transfer);
            wait(i32a, 0);
            i32a[0] = 0;
            const result = i32a[1] ? decode(i32a[1], i32a.buffer) : void 0;
            if (result instanceof Error) throw result;
            return result;
          }
          // postMessage based request
          else {
            const [uid, promise] = next();
            data[0] = uid;
            channel.postMessage(data, transfer);
            return promise;
          }
        });
      }
      return cb;
    },
    set: set$1
  });

  channel.onmessage = async ({ data }) => {
    if (typeof data[0] === 'string')
      resolve.apply(null, data);
    else {
      await result(data, proxied, transform);
      channel.postMessage(data);
    }
  };

  return {
    native: native$1,
    proxy,
    transfer: set,
  };
};

const APPLY                        = 'apply';
const CONSTRUCT                    = 'construct';
const DEFINE_PROPERTY              = 'defineProperty';
const DELETE_PROPERTY              = 'deleteProperty';
const GET                          = 'get';
const GET_OWN_PROPERTY_DESCRIPTOR  = 'getOwnPropertyDescriptor';
const GET_PROTOTYPE_OF             = 'getPrototypeOf';
const HAS                          = 'has';
const IS_EXTENSIBLE                = 'isExtensible';
const OWN_KEYS                     = 'ownKeys';
const PREVENT_EXTENSION            = 'preventExtensions';
const SET                          = 'set';
const SET_PROTOTYPE_OF             = 'setPrototypeOf';

var handlerTraps = /*#__PURE__*/Object.freeze({
  __proto__: null,
  APPLY: APPLY,
  CONSTRUCT: CONSTRUCT,
  DEFINE_PROPERTY: DEFINE_PROPERTY,
  DELETE_PROPERTY: DELETE_PROPERTY,
  GET: GET,
  GET_OWN_PROPERTY_DESCRIPTOR: GET_OWN_PROPERTY_DESCRIPTOR,
  GET_PROTOTYPE_OF: GET_PROTOTYPE_OF,
  HAS: HAS,
  IS_EXTENSIBLE: IS_EXTENSIBLE,
  OWN_KEYS: OWN_KEYS,
  PREVENT_EXTENSION: PREVENT_EXTENSION,
  SET: SET,
  SET_PROTOTYPE_OF: SET_PROTOTYPE_OF
});

const DESTRUCT = 'destruct';

/**
 * @template V
 * @param {V} value
 * @returns {Ctx<V>}
 */
const bound = value => Context.bind(value);

// This is needed to unlock *both* apply and construct
// traps otherwise one of these might fail.
// The 'use strict' directive is needed to allow
// also primitive types to be bound.
function Context() {
  return this;
}

// TODO: is this really needed in here?
// const { hasOwn } = Object;
// const isConstructable = value => hasOwn(value, 'prototype');
// const isFunction = value => typeof value === FUNCTION;

// (c) Andrea Giammarchi - ISC

const registry$2 = new FinalizationRegistry(
  ([onGarbageCollected, held, debug]) => {
    // "%cThis is a green text", "color:green"
    if (debug) console.debug(`%c${String(held)}`, 'font-weight:bold', 'collected');
    onGarbageCollected(held);
  }
);

const nullHandler = Object.create(null);

/**
 * @template {unknown} H
 * @typedef {Object} GCHookOptions
 * @prop {boolean} [debug=false] if `true`, logs values once these can get collected.
 * @prop {ProxyHandler<object>} [handler] optional proxy handler to use instead of the default one.
 * @prop {H} [return=H] if specified, overrides the returned proxy with its value.
 * @prop {unknown} [token=H] it's the held value by default, but it can be any other token except the returned value itself.
 */

/**
 * @template {unknown} H
 * @param {H} hold the reference to hold behind the scene and passed along the callback once it triggers.
 * @param {(held:H) => void} onGarbageCollected the callback that will receive the held value once its wrapper or indirect reference is no longer needed.
 * @param {GCHookOptions<H>} [options] an optional configuration object to change some default behavior.
 */
const create$2 = (
  hold,
  onGarbageCollected,
  { debug, handler, return: r, token = hold } = nullHandler
) => {
  // if no reference to return is defined,
  // create a proxy for the held one and register that instead.
  /** @type {H} */
  const target = r || new Proxy(hold, handler || nullHandler);
  const args = [target, [onGarbageCollected, hold, !!debug]];
  if (token !== false) args.push(token);
  // register the target reference in a way that
  // the `onGarbageCollected(held)` callback will eventually notify.
  registry$2.register(...args);
  return target;
};

/**
 * If previously registered as either `token` or `hold` value, allow explicit removal of the entry in the registry.
 * @param {unknown} token the token used during registration. If no `token` was passed, this can be the same `hold` reference.
 * @returns {boolean} `true` if successfully unregistered.
 */
const drop$1 = token => registry$2.unregister(token);

const { Object: Object$1, Proxy: Proxy$1, Reflect: Reflect$1 } = globalThis;

const { isArray: isArray$2 } = Array;
const { ownKeys: ownKeys$1 } = Reflect$1;
const { create: extend, hasOwn, values } = Object$1;

const wrapOf = (ref, type) => (
  type === ARRAY ? ref[0] : (
    type === FUNCTION ? ref() : (
      type === OBJECT ? ref.$ : ref
    )
  )
);

const extendHandler = (handler, type, direct, value) => {
  const descriptors = { type: { value: type } };
  const hasValueOf = hasOwn(handler, 'valueOf');
  for(const trap of values(handlerTraps)) {
    let descriptor = value(handler[trap] || Reflect$1[trap]);
    if (hasValueOf && trap === GET) {
      const { valueOf } = handler;
      const { value } = descriptor;
      descriptor = {
        value($, s, ..._) {
          return s === direct ?
            valueOf.call(this, wrapOf($, type)) :
            value.call(this, $, s, ..._);
        }
      };
    }
    descriptors[trap] = descriptor;
  }
  return extend(handler, descriptors);
};

const JSProxy = ($, target, handler, token = $) => {
  if (token === $) {
    switch (typeof $) {
      case OBJECT:
      case UNDEFINED: if (!token) token = false;
      case FUNCTION: break;
      default: {
        token = false;
        if (target === $) target = Object$1($);
      }
    }
  }
  const p = new Proxy$1(target, handler);
  const { destruct } = handler;
  return destruct ? create$2($, destruct, { token, return: p }) : p;
};

const asArrayType = value => (isArray$2(value) ? ARRAY : OBJECT);

const typeOfFor = typesOf => value => {
  const type = typeof value;
  return type === OBJECT ?
    (value ?
      (typesOf.get(value)?.[0] ?? asArrayType(value)) :
      NULL
    ) :
    type;
};

const pairFor = typesOf => value => {
  let type = typeof value;
  switch (type) {
    case OBJECT:
      if (!value) {
        type = NULL;
        break;
      }
    case FUNCTION:
      const t = typesOf.get(value);
      if (t) [type, value] = t;
      break;
  }
  return [type, value];
};

const release = token => (drop$1(token), token);

var define = namespace => {
  const typesOf = new WeakMap;
  const direct = Symbol();
  const proxy = {};
  const set = (p, type, value) => {
    typesOf.set(p, [type, value]);
    return p;
  };
  const utils = {
    proxy,
    release,
    pair: pairFor(typesOf),
    typeOf: typeOfFor(typesOf),
    isProxy: value => typesOf.has(value),
    valueOf: value => (value[direct] ?? value.valueOf()),
  };
  for (const type of ownKeys$1(namespace)) {
    if (hasOwn(utils, type)) continue;
    const traps = namespace[type];
    switch (type) {
      case ARRAY: {
        const handler = extendHandler(traps, type, direct, value => ({
          value([ $ ], ..._) {
            return value.call(this, $, ..._);
          }
        }));
        proxy[type] = ($, ..._) => set(JSProxy($, [ $ ], handler, ..._), ARRAY, $);
        break;
      }
      case FUNCTION: {
        const handler = extendHandler(traps, type, direct, value => ({
          value($, ..._) {
            return value.call(this, $(), ..._);
          }
        }));
        proxy[type] = ($, ..._) => set(JSProxy($, bound($), handler, ..._), FUNCTION, $);
        break;
      }
      case OBJECT: {
        const handler = extendHandler(traps, type, direct, value => ({
          value({ $ }, ..._) {
            return value.call(this, $, ..._);
          }
        }));
        proxy[type] = ($, ..._) => set(JSProxy($, { $ }, handler, ..._), OBJECT, $);
        break;
      }
      default: {
        const handler = extendHandler(traps, type, direct, value => ({
          value
        }));
        proxy[type] = ($, ..._) => set(JSProxy($, $, handler, ..._), type, $);
        break;
      }
    }
  }
  return utils;
};

const create$1 = () => {
  const ids = new Map;
  const values = new Map;
  let uid = 0;
  return {
    /**
     * Clear all references retained in the current heap.
     */
    clear: () => {
      ids.clear();
      values.clear();
    },

    /**
     * Remove by id or value any previously stored reference.
     * @param {number | unknown} id the held value by id or the value itself.
     * @returns {boolean} `true` if the operation was successful, `false` otherwise.
     */
    drop: id => {
      const [a, b] = typeof id === NUMBER ? [values, ids] : [ids, values];
      const had = a.has(id);
      if (had) {
        b.delete(a.get(id));
        a.delete(id);
      }
      return had;
    },

    /**
     * Return the held value reference by its unique identifier.
     * @param {number} id the unique identifier for the value reference.
     * @returns {unknown} the related value / reference or undefined.
     */
    get: id => values.get(id),

    /**
     * Create once a unique number id for a generic value reference.
     * @param {unknown} value a reference used to create a unique identifier.
     * @returns {number} a unique identifier for that reference.
     */
    hold: value => {
      if (!ids.has(value)) {
        let id;
        // a bit apocalyptic scenario but if this thread runs forever
        // and the id does a whole int32 roundtrip we might have still
        // some reference dangling around
        while (/* c8 ignore next */ values.has(id = uid++));
        ids.set(value, id);
        values.set(id, value);
      }
      return ids.get(value);
    },
  };
};

// globally shared heap
const { drop, get, hold } = create$1();

const symbols = new Map;

for (const s of Reflect.ownKeys(Symbol)) {
  if (typeof Symbol[s] === SYMBOL) {
    symbols.set(Symbol[s], s);
    symbols.set(s, Symbol[s]);
  }
}

const fromSymbol = value => (
  symbols.get(value) ||
  Symbol.for(value.slice(1))
);

const toSymbol = value => (
  symbols.get(value) ||
  `.${Symbol.keyFor(value) || ''}`
);

const { isArray: isArray$1 } = Array;
const { isView } = ArrayBuffer;

const { [APPLY]: apply$1 } = Reflect;

var proxyWorker = (__main__, transform) => {
  const proxies = new Map;
  const proxied = (value, proxy) => {
    let ref = proxies.get(value)?.deref();
    if (!ref) proxies.set(value, new WeakRef((ref = proxy(value))));
    return ref;
  };

  const fromEntry = ([numericTYPE, value]) => {
    switch (numericTYPE) {
      case numeric[OBJECT]: return (
        value == null ?
          globalThis :
          typeof value === NUMBER ?
            proxied(value, proxy.object) :
            value
      );
      case numeric[ARRAY]: return typeof value === NUMBER ? proxied(value, proxy.array) : value;
      case numeric[FUNCTION]: return (
        typeof value === NUMBER ?
          proxied(value, proxy.function) :
          get(parseInt(value))
      );
      case numeric[SYMBOL]: return fromSymbol(value);
      default: return value;
    }
  };

  const toEntry = value => {
    let [TYPE, ref] = pair(value);
    switch (TYPE) {
      case OBJECT: {
        if (ref == globalThis || ref == null) ref = null;
        else if ((typeof ref === OBJECT)) {
          ref = transform(ref);
          // this happens with proxies recognized as objects
          // but that could reveal an array underneath
          if (isArray$1(ref)) return [numeric[ARRAY], ref.map(toEntry)];
          if (isView(ref)) return [numeric.view, ref];
          else {
            const result = {};
            for (const key in ref) result[key] = toEntry(ref[key]);
            ref = result;
          }
        }
        return [numeric[OBJECT], ref];
      }
      case ARRAY: {
        return [numeric[ARRAY], typeof ref === NUMBER ? ref : transform(ref).map(toEntry)];
      }
      case FUNCTION: {
        // own local functions as String(id)
        return [numeric[FUNCTION], typeof ref === FUNCTION ? String(hold(transform(ref))) : ref];
      }
      case SYMBOL: return [numeric[SYMBOL], toSymbol(value)];
      default: return [numeric[TYPE], ref];
    }
  };

  const asEntry = (...args) => fromEntry(__main__(...args));

  const handler = {
    [DEFINE_PROPERTY]: (ref, name, descriptor) => asEntry(DEFINE_PROPERTY, ref, toEntry(name), toEntry(descriptor)),
    [DELETE_PROPERTY]: (ref, name) => asEntry(DELETE_PROPERTY, ref, toEntry(name)),
    [GET]: (ref, name) => asEntry(GET, ref, toEntry(name)),
    [GET_PROTOTYPE_OF]: (ref) => asEntry(GET_PROTOTYPE_OF, ref),
    [GET_OWN_PROPERTY_DESCRIPTOR]: (ref, name) => {
      const descriptor = asEntry(GET_OWN_PROPERTY_DESCRIPTOR, ref, toEntry(name));
      if (descriptor) {
        const { get, set, value } = descriptor;
        if (get) descriptor.get = fromEntry(get);
        if (set) descriptor.set = fromEntry(set);
        if (value) descriptor.value = fromEntry(value);
      }
      return descriptor;
    },
    [HAS]: (ref, name) => asEntry(HAS, ref, toEntry(name)),
    [IS_EXTENSIBLE]: (ref) => asEntry(IS_EXTENSIBLE, ref),
    [OWN_KEYS]: (ref) => asEntry(OWN_KEYS, ref).map(fromEntry),
    [PREVENT_EXTENSION]: (ref) => asEntry(PREVENT_EXTENSION, ref),
    [SET]: (ref, name, value) => asEntry(SET, ref, toEntry(name), toEntry(value)),
    [SET_PROTOTYPE_OF]: (ref, proto) => asEntry(SET_PROTOTYPE_OF, ref, toEntry(proto)),

    [DESTRUCT](ref) {
      proxies.delete(ref);
      __main__(DESTRUCT, ref);
    },
  };

  const definition = {
    [OBJECT]: handler,
    [ARRAY]: handler,
    [FUNCTION]: {
      ...handler,
      [APPLY]: (ref, ...args) => asEntry(APPLY, ref, ...args.map(toEntry)),
      [CONSTRUCT]: (ref, ...args) => asEntry(CONSTRUCT, ref, ...args.map(toEntry)),
    },
  };

  const { proxy, isProxy, pair } = define(definition);

  return {
    isProxy,
    global: proxy.object(null),
    method: async (TRAP, ref, ...args) => {
      const id = parseInt(ref);
      switch (TRAP) {
        case APPLY: {
          const [self, params] = args;
          return toEntry(await apply$1(
            get(id),
            fromEntry(self),
            params.map(fromEntry)
          ));
        }
        case DESTRUCT: {
          drop(id);
        }
      }
    }
  };
};

/**
 * @callback Coincident
 * @param {import('../worker.js').WorkerOptions} [options]
 * @returns {Promise<{native: boolean, transfer: (...args: Transferable[]) => Transferable[], proxy: {}, window: Window, isWindowProxy: (value: any) => boolean}>}
 */

var coincident = /** @type {Coincident} */ async options => {
  let tracking = false;
  const defaultDecoder = options?.decoder || decoder$2;
  const exports = await coincident$1({
    ...options,
    decoder(options) {
      const original = defaultDecoder(options);
      const minimal = decoder$1(options);
      return (length, buffer) => {
        if (tracking) {
          tracking = false;
          return minimal(length, buffer);
        }
        return original(length, buffer);
      };
    }
  });

  const main = exports.proxy[MAIN];

  const { isProxy, global, method } = proxyWorker(
    function (...args) {
      tracking = true;
      return main.apply(this, args);
    },
    options?.transform || ((o) => o)
  );

  // for the time being this is used only to invoke callbacks
  // attached as listeners or as references' fields.
  exports.proxy[WORKER] = method;

  return { ...exports, window: global, isWindowProxy: isProxy };
};

function content (t) {
  for (var s = t[0], i = 1, l = arguments.length; i < l; i++)
    s += arguments[i] + t[i];
  return s;
}

const dedent$1 = {
  object(...args) {
    return this.string(content(...args));
  },
  string(content) {
    for (const line of content.split(/[\r\n]+/)) {
      // skip initial empty lines
      if (line.trim().length) {
        // trap indentation at the very first line of code
        if (/^(\s+)/.test(line))
          content = content.replace(new RegExp('^' + RegExp.$1, 'gm'), '');
        // no indentation? all good: get out of here!
        break;
      }
    }
    return content;
  }
};

/**
 * Usable both as template literal tag or just as callback for strings, removes all spaces found
 * at the very first line of code encountered while sanitizing, keeping everything else around.
 * @param {string | TemplateStringsArray} tpl either code as string or as template, when used as tag
 * @param  {...any} values the template interpolations, when used as tag
 * @returns {string} code without undesired indentation
 */
const codedent = (tpl, ...values) => dedent$1[typeof tpl](tpl, ...values);

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const io = new WeakMap();
const stdio = (init) => {
    const context = init || console;
    const localIO = {
        // allow plugins or other io manipulating logic to reuse
        // the buffered utility exposed in here (see py-editor)
        buffered,
        stderr: (context.stderr || console.error).bind(context),
        stdout: (context.stdout || console.log).bind(context),
    };
    return {
        stderr: (...args) => localIO.stderr(...args),
        stdout: (...args) => localIO.stdout(...args),
        async get(engine) {
            const interpreter = await engine;
            io.set(interpreter, localIO);
            return interpreter;
        },
    };
};

const decoder = new TextDecoder();
const buffered = (callback, EOL = 10) => {
    const buffer = [];
    return (maybeUI8) => {
        if (maybeUI8 instanceof Uint8Array) {
            for (const c of maybeUI8) {
                if (c === EOL)
                    callback(decoder.decode(new Uint8Array(buffer.splice(0))));
                else
                    buffer.push(c);
            }
        }
        // if io.stderr(error) is passed instead
        // or any io.stdout("thing") this should
        // still work as expected
        else {
            callback(maybeUI8);
        }
    };
};
/* c8 ignore stop */

/** @type {(tpl: string | TemplateStringsArray, ...values:any[]) => string} */
const dedent = codedent;

const { isArray } = Array;

const { assign, create, defineProperty, entries } = Object;

const { all, resolve: resolve$1 } = new Proxy(Promise, {
    get: ($, name) => $[name].bind($),
});

const absoluteURL = (path, base = location.href) =>
    new URL(path, base.replace(/^blob:/, '')).href;

function fixedRelative(path) {
    return path.startsWith('.') ? absoluteURL(path, this) : path;
}

/**
 * Notify the main thread about element "readiness".
 * @param {HTMLScriptElement | HTMLElement} target the script or custom-type element
 * @param {string} type the custom/type as event prefix
 * @param {string} what the kind of event to dispatch, i.e. `ready` or `done`
 * @param {boolean} [worker = false] `true` if dispatched form a worker, `false` by default if in main
 * @param {globalThis.CustomEvent} [CustomEvent = globalThis.CustomEvent] the `CustomEvent` to use
 */
const dispatch = (target, type, what, worker = false, CE = CustomEvent) => {
    target.dispatchEvent(
        new CE(`${type}:${what}`, {
            bubbles: true,
            detail: { worker },
        })
    );
};

const createFunction = value => Function(`'use strict';return (${value})`)();

const createResolved = (module, type, config, interpreter) => ({
    type,
    config,
    interpreter,
    io: io.get(interpreter),
    run: (code, ...args) => module.run(interpreter, code, ...args),
    runAsync: (code, ...args) => module.runAsync(interpreter, code, ...args),
    runEvent: (...args) => module.runEvent(interpreter, ...args),
});

const dropLine0 = code => code.replace(/^(?:\n|\r\n)/, '');

const createOverload = (module, name, before, after) => {
    const method = module[name].bind(module);
    module[name] = name === 'run' ?
        // patch the sync method
        (interpreter, code, ...args) => {
            if (before) method(interpreter, before, ...args);
            const result = method(interpreter, dropLine0(code), ...args);
            if (after) method(interpreter, after, ...args);
            return result;
        } :
        // patch the async one
        async (interpreter, code, ...args) => {
            if (before) await method(interpreter, before, ...args);
            const result = await method(interpreter, dropLine0(code), ...args);
            if (after) await method(interpreter, after, ...args);
            return result;
        };
};

const js_modules = Symbol.for('polyscript.js_modules');

const jsModules = new Map;
defineProperty(globalThis, js_modules, { value: jsModules });

new Proxy(jsModules, {
    get: (map, name) => map.get(name),
    has: (map, name) => map.has(name),
    ownKeys: map => [...map.keys()],
});

const has$1 = (_, field) => !field.startsWith('_');

const proxy$1 = (modules, name) => new Proxy(
    modules,
    { has: has$1, get: (modules, field) => modules[name][field] }
);

const registerJSModules = (type, module, interpreter, modules) => {
    // Pyodide resolves JS modules magically
    if (type === 'pyodide') return;

    // other runtimes need this pretty ugly dance (it works though)
    const jsModules = 'polyscript.js_modules';
    for (const name of Reflect.ownKeys(modules))
        module.registerJSModule(interpreter, `${jsModules}.${name}`, proxy$1(modules, name));
    module.registerJSModule(interpreter, jsModules, modules);
};

const importJS = (source, name) => import(source).then(esm => {
    jsModules.set(name, { ...esm });
});

const importCSS = href => new Promise((onload, onerror) => {
    if (document.querySelector(`link[rel="stylesheet"][href="${href}"]`)) {
        onload();
    }
    else {
        document.head.append(
            assign(
                document.createElement('link'),
                { rel: 'stylesheet', href, onload, onerror },
            )
        );
    }
});

const isCSS = source => /\.css$/i.test(new URL(source).pathname);

const has = (modules, name) => modules.has(name);

const ownKeys = modules => [...modules.keys()];

const proxy = (modules, window, sync, baseURL) => new Proxy(modules, {
    has,
    ownKeys,
    get: (modules, name) => {
        let value = modules.get(name);
        if (isArray(value)) {
            let sources = value;
            value = null;
            for (let source of sources) {
                source = absoluteURL(source, baseURL);
                if (isCSS(source)) sync.importCSS(source);
                else {
                    sync.importJS(source, name);
                    value = window[js_modules].get(name);
                }
            }
            modules.set(name, value);
        }
        return value;
    },
});

var createJSModules = (window, sync, mainModules, baseURL) => {
    const modules = globalThis[js_modules];
    if (mainModules) {
        for (let [source, module] of entries(mainModules)) {
            let value = modules.get(module);
            if (!value || isArray(value)) {
                modules.set(module, value || (value = []));
                value.push(source);
            }
        }
    }
    return proxy(modules, window, sync, baseURL);
};

const registry$1 = new Map;

const type$5 = 'dummy';

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const require = name => registry$1.get(name);

const run$2 = (interpreter, code) => {
    try {
        return Function('require', code)(require);
    }
    catch (error) {
        io.get(interpreter).stderr(error);
    }
};

var dummy = {
    type: type$5,
    module: () => 'data:text/javascript,',
    engine: module => stdio().get(module),
    registerJSModule(_, name, value) {
        registry$1.set(name, value);
    },
    run: run$2,
    runAsync: run$2,
    runEvent: async (interpreter, code, event) => {
        try {
            await Function('require', 'e', `return ${code}(e)`)(require, event);
        }
        catch (error) {
            io.get(interpreter).stderr(error);
        }
    },
    transform: (_, value) => value,
    writeFile() {},
};

// a bit terser code than I usually write but it's 10 LOC within 80 cols
// if you are struggling to follow the code you can replace 1-char
// references around with the following one, hoping that helps :-)

// d => descriptors
// k => key
// p => promise
// r => response

const d = Object.getOwnPropertyDescriptors(Response.prototype);

const isFunction = value => typeof value === 'function';

const bypass = (p, k, { get, value }) => get || !isFunction(value) ?
                p.then(r => r[k]) :
                (...args) => p.then(r => r[k](...args));

const direct = (p, value) => isFunction(value) ? value.bind(p) : value;

const handler = {
    get: (p, k) => d.hasOwnProperty(k) ? bypass(p, k, d[k]) : direct(p, p[k])
};

/**
 * @param {RequestInfo | URL} input
 * @param  {...RequestInit} init
 * @returns {Promise<Response> & Response}
 */
var fetch$1 = (input, ...init) => new Proxy(fetch(input, ...init), handler);

const RUNNING_IN_WORKER = !globalThis.window;

// REQUIRES INTEGRATION TEST
/* c8 ignore start */

// This should be the only helper needed for all Emscripten based FS exports
const writeFile = ({ FS, PATH, PATH_FS }, path, buffer) => {
    const absPath = PATH_FS.resolve(path);
    const dirPath = PATH.dirname(absPath);
    if (FS.mkdirTree) FS.mkdirTree(dirPath);
    else mkdirTree(FS, dirPath);
    return FS.writeFile(absPath, new Uint8Array(buffer), {
        canOwn: true,
    });
};

// This is instead a fallback for Lua or others
const writeFileShim = (FS, path, buffer) => {
    mkdirTree(FS, dirname(path));
    path = resolve(FS, path);
    return FS.writeFile(path, new Uint8Array(buffer), { canOwn: true });
};

const dirname = (path) => {
    const tree = path.split('/');
    tree.pop();
    return tree.join('/');
};

const mkdirTree = (FS, path) => {
    const current = [];
    for (const branch of path.split('/')) {
        if (branch === '.' || branch === '..') continue;
        current.push(branch);
        if (branch) FS.mkdir(current.join('/'));
    }
};

const resolve = (FS, path) => {
    const tree = [];
    for (const branch of path.split('/')) {
        switch (branch) {
            case '':
                break;
            case '.':
                break;
            case '..':
                tree.pop();
                break;
            default:
                tree.push(branch);
        }
    }
    return [FS.cwd()].concat(tree).join('/').replace(/^\/+/, '/');
};

const calculateFetchPaths = (config_fetch) => {
    for (const { files, to_file, from = '' } of config_fetch) {
        if (files !== undefined && to_file !== undefined)
            throw new Error(
                'Cannot use \'to_file\' and \'files\' parameters together!',
            );
        if (files === undefined && to_file === undefined && from.endsWith('/'))
            throw new Error(
                `Couldn't determine the filename from the path ${from}, please supply 'to_file' parameter.`,
            );
    }
    return config_fetch.flatMap(
        ({ from = '', to_folder = '.', to_file, files }) => {
            if (isArray(files))
                return files.map((file) => ({
                    url: joinPaths([from, file]),
                    path: joinPaths([to_folder, file]),
                }));
            const filename = to_file || from.slice(1 + from.lastIndexOf('/'));
            return [{ url: from, path: joinPaths([to_folder, filename]) }];
        },
    );
};

const joinPaths = (parts) => {
    const res = parts
        .map((part) => part.trim().replace(/(^[/]*|[/]*$)/g, ''))
        .filter((p) => p !== '' && p !== '.')
        .join('/');

    return parts[0].startsWith('/') ? `/${res}` : res;
};

const fetchBuffer = (url, baseURL) =>
    fetch$1(absoluteURL(url, baseURL)).arrayBuffer();

const fetchPaths = (module, interpreter, config_fetch, baseURL) =>
    all(
        calculateFetchPaths(config_fetch).map(({ url, path }) =>
            fetchBuffer(url, baseURL)
                .then((buffer) => module.writeFile(interpreter, path, buffer)),
        ),
    );

    const fillName = (source, dest) => dest.endsWith('/') ?
                        `${dest}${source.split('/').pop()}` : dest;

const parseTemplate = (src, map) => src.replace(
  /\{.+?\}/g,
  k => {
    if (!map.has(k))
      throw new SyntaxError(`Invalid template: ${k}`);
    return map.get(k);
  }
);

const calculateFilesPaths = files => {
  const map = new Map;
  const targets = new Set;
  const sourceDest = [];
  for (const [source, dest] of entries(files)) {
    if (/^\{.+\}$/.test(source)) {
      if (map.has(source))
        throw new SyntaxError(`Duplicated template: ${source}`);
      map.set(source, parseTemplate(dest, map));
    }
    else {
      const url = parseTemplate(source, map);
      const path = fillName(url, parseTemplate(dest || './', map));
      if (targets.has(path) && !path.endsWith('/*'))
        throw new SyntaxError(`Duplicated destination: ${path}`);
      targets.add(path);
      sourceDest.push({ url, path });
    }
  }
  return sourceDest;
};

const fetchFiles = (module, interpreter, config_files, baseURL) =>
    all(
        calculateFilesPaths(config_files).map(({ url, path }) =>
            fetchBuffer(url, baseURL)
                .then((buffer) => module.writeFile(
                    interpreter,
                    path,
                    buffer,
                    url,
                )),
        ),
    );

const fetchJSModules = ({ main, worker }, baseURL) => {
    const promises = [];
    if (worker && RUNNING_IN_WORKER) {
        for (let [source, name] of entries(worker)) {
            source = absoluteURL(source, baseURL);
            promises.push(importJS(source, name));
        }
    }
    if (main && !RUNNING_IN_WORKER) {
        for (let [source, name] of entries(main)) {
            source = absoluteURL(source, baseURL);
            if (isCSS(source)) importCSS(source);
            else promises.push(importJS(source, name));
        }
    }
    return all(promises);
};

const createProgress = prefix => detail => {
    dispatchEvent(new CustomEvent(`${prefix}:progress`, { detail }));
};
/* c8 ignore stop */

const{getPrototypeOf:e}=Object,r$1=e=>{const r=typeof e;switch(r){case "function":case "undefined":return "";case "object":return null===e?"null":"object";default:return r}};let t="coincident-";try{new SharedArrayBuffer(4,{maxByteLength:8}),t+=crypto.randomUUID();}catch(e){t+=Math.random().toString(36).substring(2);}var n={ref:0,array:1,object:2,number:3,string:4,true:5,false:6,null:7,buffer:8,view:9,symbol:10,date:11,bigint:12,undefined:13,map:14,set:15,regexp:16,error:17};const{defineProperty:s}=Object,a=e=>{switch(e[c++]){case n.array:{const r=e[c++],t=[];e[c-2]=t;for(let n=0;n<r;n++)t[n]=a(e);return t}case n.object:{const r=e[c++],t={};e[c-2]=t;for(let n=0;n<r;n++)t[a(e)]=a(e);return t}case n.string:{const r=e[c++];return e[c-2]=r,r}case n.number:return e[c++];case n.true:return  true;case n.false:return  false;case n.null:return null;case n.undefined:return;case n.bigint:return BigInt(e[c++]);case n.buffer:{const r=e[c++],t=e[c++],n=[r];t&&n.push({maxByteLength:t});const s=new ArrayBuffer(...n);e[c-3]=s;const a=new Uint8Array(s,0,r);for(let t=0;t<r;t++)a[t]=e[c++];return s}case n.view:{const r=e[c++],t=e[c++],n=e[c++],s=c-4,o=[a(e),t];n&&o.push(n);const u=new globalThis[r](...o);return e[s]=u,u}case n.date:{const r=new Date(e[c++]);return e[c-2]=r,r}case n.map:{const r=e[c++],t=new Map;e[c-2]=t;for(let n=0;n<r;n++){const r=a(e),n=a(e);void 0!==r&&t.set(r,n);}return t}case n.set:{const r=e[c++],t=new Set;e[c-2]=t;for(let n=0;n<r;n++){const r=a(e);void 0!==r&&t.add(r);}return t}case n.regexp:{const r=e[c++],t=e[c++],n=new RegExp(r,t);return e[c-3]=n,n}case n.error:{const r=globalThis[e[c++]]||Error,t=e[c++],n=e[c++],a=new r(t,{cause:e[c++]});return e[c-5]=s(a,"stack",{value:n}),a}case n.symbol:return (r=e[c++]).startsWith("Symbol.")?Symbol[r.slice(r.indexOf(".")+1)]:Symbol.for(r);case n.ref:return e[e[c++]];default:throw new TypeError(`Unknown type: ${e[c-1]}`)}var r;},{parse:o}=JSON;let c=0;const u=e=>{return r=o(e),c=0,r.length?a(r):void 0;var r;},{isArray:i}=Array,{isView:f}=ArrayBuffer,{stringify:l}=JSON,b=(e,r,t)=>{const s=r.get(t);return "number"==typeof s?(e.push(n.ref,s),true):(r.set(t,e.length),false)},h=(t,s,a,o=r$1(a))=>{switch(o){case "null":t.push(n.null);break;case "object":if(b(t,s,a))break;switch(true){case i(a):{const e=a.length;t.push(n.array,e);for(let r=0;r<e;r++)h(t,s,a[r]);break}case f(a):{const{BYTES_PER_ELEMENT:r,buffer:o,byteOffset:c,length:u}=a;if(t.push(n.view,(r=>{for(;!(r.name in globalThis);)r=e(r);return r.name})(a.constructor),c,u!==(o.byteLength-c)/r?u:0),b(t,s,o))break;a=o;}case a instanceof ArrayBuffer:{const e=a.byteLength,r=a.resizable?a.maxByteLength:0;if(t.push(n.buffer,e,r),e){const r=new Uint8Array(a,0,e);for(let e=0;e<r.length;e+=32767)t.push.apply(t,r.subarray(e,e+32767));}break}case a instanceof Date:t.push(n.date,+a);break;case a instanceof Map:{const e=t.push(n.map,0);let o=0;for(const[e,n]of a){const a=r$1(e),c=r$1(n);a&&c&&(h(t,s,e,a),h(t,s,n,c),o++);}t[e-1]=o;break}case a instanceof Set:{const e=t.push(n.set,0);let o=0;for(const e of a){const n=r$1(e);n&&(h(t,s,e,n),o++);}t[e-1]=o;break}case a instanceof RegExp:t.push(n.regexp,a.source,a.flags);break;case a instanceof Error:t.push(n.error,a.name,a.message,a.stack,a.cause);break;default:{if("toJSON"in a){const e=a.toJSON();if(e===a){t.push(n.object,0);break}if(b(t,s,a=e))break}const e=t.push(n.object,0);let o=0;for(const e in a){const n=a[e],c=r$1(n);c&&(h(t,s,e,"string"),h(t,s,n,c),o++);}t[e-1]=o;break}}break;case "boolean":t.push(a?n.true:n.false);break;case "string":if(b(t,s,a))break;t.push(n.string,a);break;case "bigint":t.push(n.bigint,a.toString());break;case "symbol":{const e=(e=>{const r=String(e).slice(7,-1);return r.startsWith("Symbol.")||Symbol.keyFor(e)?r:""})(a);if(e){t.push(n.symbol,e);break}}case "":t.push(n.undefined);break;default:t.push(n[o],a);}},p=e=>l((e=>{const r=[];return h(r,new Map,e),r})(e));

const JSON$1 = { parse: u, stringify: p };

const loader = new WeakMap();

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const loadProgress = async (self, progress, interpreter, config, baseURL) => {
    if (config.files) {
        progress('Loading files');
        await fetchFiles(self, interpreter, config.files, baseURL);
        progress('Loaded files');
    }
    if (config.fetch) {
        progress('Loading fetch');
        await fetchPaths(self, interpreter, config.fetch, baseURL);
        progress('Loaded fetch');
    }
    if (config.js_modules) {
        progress('Loading JS modules');
        await fetchJSModules(config.js_modules, baseURL);
        progress('Loaded JS modules');
    }
};

const registerJSModule = (interpreter, name, value) => {
    if (name === 'polyscript') {
        value.lazy_py_modules = async (...packages) => {
            await loader.get(interpreter)(packages);
            return packages.map(name => interpreter.pyimport(name));
        };
        value.storage = async (name) => {
            const storage = new IDBMapSync(name);
            await storage.sync();
            return storage;
        };
        value.JSON = JSON$1;
    }
    interpreter.registerJsModule(name, value);
};

const getFormat = (path, url) => {
    if (path.endsWith('/*')) {
        if (/\.(zip|whl|tgz|tar(?:\.gz)?)$/.test(url))
            return RegExp.$1;
        throw new Error(`Unsupported archive ${url}`);
    }
    return '';
};

const run$1 = (interpreter, code, ...args) => {
    try {
        return interpreter.runPython(dedent(code), ...args);
    }
    catch (error) {
        io.get(interpreter).stderr(error);
    }
};

const runAsync = async (interpreter, code, ...args) => {
    try {
        return await interpreter.runPythonAsync(dedent(code), ...args);
    }
    catch (error) {
        io.get(interpreter).stderr(error);
    }
};

const runEvent$1 = async (interpreter, code, event) => {
    // allows method(event) as well as namespace.method(event)
    // it does not allow fancy brackets names for now
    const [name, ...keys] = code.split('.');
    let target = interpreter.globals.get(name);
    let context;
    for (const key of keys) [context, target] = [target, target[key]];
    try {
        await target.call(context, event);
    }
    catch (error) {
        io.get(interpreter).stderr(error);
    }
};
/* c8 ignore stop */

// ⚠️ DO NOT MODIFY - SOURCE FILE: "../../python/mip.py"
var mip = new TextEncoder().encode("_F='github:'\n_E='user-agent'\n_D=True\n_C=False\n_B='/'\n_A=None\nfrom uio import StringIO\nimport sys\nclass Response:\n\tdef __init__(A,f):A.raw=f;A.encoding='utf-8';A._cached=_A\n\tdef close(A):\n\t\tif A.raw:A.raw.close();A.raw=_A\n\t\tA._cached=_A\n\t@property\n\tdef content(self):\n\t\tA=self\n\t\tif A._cached is _A:\n\t\t\ttry:A._cached=A.raw.read()\n\t\t\tfinally:A.raw.close();A.raw=_A\n\t\treturn A._cached\n\t@property\n\tdef text(self):return str(self.content,self.encoding)\n\tdef json(A):import ujson;return ujson.loads(A.content)\nHEADERS_TO_IGNORE=_E,\ntry:import js\nexcept Exception as err:raise OSError('This version of urequests can only be used in the browser')\nHEADERS_TO_IGNORE=_E,\ndef request(method,url,data=_A,json=_A,headers={},stream=_A,auth=_A,timeout=_A,parse_headers=_D):\n\tE=timeout;D=method;C=data;from js import XMLHttpRequest as G;A=G.new();A.withCredentials=_C\n\tif auth is not _A:import ubinascii;H,I=auth;A.open(D,url,_C,H,I)\n\telse:A.open(D,url,_C)\n\tfor(F,J)in headers.items():\n\t\tif F.lower()not in HEADERS_TO_IGNORE:A.setRequestHeader(F,J)\n\tif E:A.timeout=int(E*1000)\n\tif json is not _A:assert C is _A;import ujson;C=ujson.dumps(json);A.setRequestHeader('Content-Type','application/json')\n\tA.send(C);B=Response(StringIO(A.responseText));B.status_code=A.status;B.reason=A.statusText;B.headers=A.getAllResponseHeaders();return B\ndef get(url,**A):return request('GET',url,**A)\n_PACKAGE_INDEX=const('https://micropython.org/pi/v2')\n_CHUNK_SIZE=128\ndef _ensure_path_exists(path):\n\timport os;A=path.split(_B)\n\tif not A[0]:A.pop(0);A[0]=_B+A[0]\n\tB=''\n\tfor C in range(len(A)-1):\n\t\tB+=A[C]\n\t\ttry:os.stat(B)\n\t\texcept:os.mkdir(B)\n\t\tB+=_B\ndef _chunk(src,dest):\n\tA=memoryview(bytearray(_CHUNK_SIZE))\n\twhile _D:\n\t\tB=src.readinto(A)\n\t\tif B==0:break\n\t\tdest(A if B==_CHUNK_SIZE else A[:B])\ndef _check_exists(path,short_hash):\n\tA=short_hash;import os\n\ttry:\n\t\timport binascii as C,hashlib as D\n\t\twith open(path,'rb')as E:B=D.sha256();_chunk(E,B.update);F=str(C.hexlify(B.digest())[:len(A)],'utf-8');return F==A\n\texcept:return _C\ndef _rewrite_url(url,branch=_A):\n\tB=branch;A=url\n\tif not B:B='HEAD'\n\tif A.startswith(_F):A=A[7:].split(_B);A='https://raw.githubusercontent.com/'+A[0]+_B+A[1]+_B+B+_B+_B.join(A[2:])\n\treturn A\ndef _download_file(url,dest):\n\tB=dest;A=get(url)\n\ttry:\n\t\tif A.status_code!=200:print('Error',A.status_code,'requesting',url);return _C\n\t\tprint('Copying:',B);_ensure_path_exists(B)\n\t\twith open(B,'wb')as C:_chunk(A.raw,C.write)\n\t\treturn _D\n\tfinally:A.close()\ndef _install_json(package_json_url,index,target,version,mpy):\n\tK='File not found: {} {}';I=version;H=index;G=package_json_url;D=target;E=get(_rewrite_url(G,I))\n\ttry:\n\t\tif E.status_code!=200:print('Package not found:',G);return _C\n\t\tF=E.json()\n\tfinally:E.close()\n\tfor(A,C)in F.get('hashes',()):\n\t\tB=D+_B+A\n\t\tif _check_exists(B,C):print('Exists:',B)\n\t\telse:\n\t\t\tL='{}/file/{}/{}'.format(H,C[:2],C)\n\t\t\tif not _download_file(L,B):print(K.format(A,C));return _C\n\tfor(A,J)in F.get('urls',()):\n\t\tB=D+_B+A\n\t\tif not _download_file(_rewrite_url(J,I),B):print(K.format(A,J));return _C\n\tfor(M,N)in F.get('deps',()):\n\t\tif not _install_package(M,H,D,N,mpy):return _C\n\treturn _D\ndef _install_package(package,index,target,version,mpy):\n\tD=index;C=target;B=version;A=package\n\tif A.startswith('http://')or A.startswith('https://')or A.startswith(_F):\n\t\tif A.endswith('.py')or A.endswith('.mpy'):print('Downloading {} to {}'.format(A,C));return _download_file(_rewrite_url(A,B),C+_B+A.rsplit(_B)[-1])\n\t\telse:\n\t\t\tif not A.endswith('.json'):\n\t\t\t\tif not A.endswith(_B):A+=_B\n\t\t\t\tA+='package.json'\n\t\t\tprint('Installing {} to {}'.format(A,C))\n\telse:\n\t\tif not B:B='latest'\n\t\tprint('Installing {} ({}) from {} to {}'.format(A,B,D,C));E=sys.implementation._mpy&255 if mpy and hasattr(sys.implementation,'_mpy')else'py';A='{}/package/{}/{}/{}.json'.format(D,'py',A,B)\n\treturn _install_json(A,D,C,B,mpy)\ndef install(package,index=_A,target=_A,version=_A,mpy=_D):\n\tB=target;A=index\n\tif not B:\n\t\tfor C in sys.path:\n\t\t\tif C.endswith('/lib'):B=C;break\n\t\telse:print('Unable to find lib dir in sys.path');return\n\tif not A:A=_PACKAGE_INDEX\n\tif _install_package(package,A.rstrip(_B),B,version,mpy):print('Done')\n\telse:print('Package may be partially installed')");

/* c8 ignore start */

// toml
const toml = async (text) => (
  await import(/* webpackIgnore: true */'./toml-CkEFU7ly.js')
).parse(text);

// zip
const zip = () => import(/* webpackIgnore: true */'./zip-CAMAhqMX.js');

/* c8 ignore stop */

async function syncfs(FS, direction) {
    return new Promise((resolve, reject) => {
        FS.syncfs(direction, err => {
            if (err) reject(err);
            else resolve();
        });
    });
}

// (C) Pyodide  https://github.com/pyodide/pyodide - Mozilla Public License Version 2.0
// JS port of https://github.com/pyodide/pyodide/blob/34fcd02172895d75db369994011409324f9e3cce/src/js/nativefs.ts
function initializeNativeFS(module) {
    const FS = module.FS;
    const MEMFS = module.FS.filesystems.MEMFS;
    const PATH = module.PATH;

    const nativeFSAsync = {
        // DIR_MODE: {{{ cDefine('S_IFDIR') }}} | 511 /* 0777 */,
        // FILE_MODE: {{{ cDefine('S_IFREG') }}} | 511 /* 0777 */,
        DIR_MODE: 16384 | 511,
        FILE_MODE: 32768 | 511,
        mount: function (mount) {
            if (!mount.opts.fileSystemHandle) {
                throw new Error('opts.fileSystemHandle is required');
            }

            // reuse all of the core MEMFS functionality
            return MEMFS.mount.apply(null, arguments);
        },
        syncfs: async (mount, populate, callback) => {
            try {
                const local = nativeFSAsync.getLocalSet(mount);
                const remote = await nativeFSAsync.getRemoteSet(mount);
                const src = populate ? remote : local;
                const dst = populate ? local : remote;
                await nativeFSAsync.reconcile(mount, src, dst);
                callback(null);
            } catch (e) {
                callback(e);
            }
        },
        // Returns file set of emscripten's filesystem at the mountpoint.
        getLocalSet: (mount) => {
            let entries = Object.create(null);

            function isRealDir(p) {
                return p !== '.' && p !== '..';
            }

            function toAbsolute(root) {
                return (p) => {
                    return PATH.join2(root, p);
                };
            }

            let check = FS.readdir(mount.mountpoint)
                .filter(isRealDir)
                .map(toAbsolute(mount.mountpoint));

            while (check.length) {
                let path = check.pop();
                let stat = FS.stat(path);

                if (FS.isDir(stat.mode)) {
                    check.push.apply(
                        check,
                        FS.readdir(path).filter(isRealDir).map(toAbsolute(path)),
                    );
                }

                entries[path] = { timestamp: stat.mtime, mode: stat.mode };
            }

            return { type: 'local', entries: entries };
        },
        // Returns file set of the real, on-disk filesystem at the mountpoint.
        getRemoteSet: async (mount) => {
            // TODO: this should be a map.
            const entries = Object.create(null);

            const handles = await getFsHandles(mount.opts.fileSystemHandle);
            for (const [path, handle] of handles) {
                if (path === '.') continue;

                entries[PATH.join2(mount.mountpoint, path)] = {
                    timestamp:
                        handle.kind === 'file'
                            ? (await handle.getFile()).lastModifiedDate
                            : new Date(),
                    mode:
                        handle.kind === 'file'
                            ? nativeFSAsync.FILE_MODE
                            : nativeFSAsync.DIR_MODE,
                };
            }

            return { type: 'remote', entries, handles };
        },
        loadLocalEntry: (path) => {
            const lookup = FS.lookupPath(path);
            const node = lookup.node;
            const stat = FS.stat(path);

            if (FS.isDir(stat.mode)) {
                return { timestamp: stat.mtime, mode: stat.mode };
            } else if (FS.isFile(stat.mode)) {
                node.contents = MEMFS.getFileDataAsTypedArray(node);
                return {
                    timestamp: stat.mtime,
                    mode: stat.mode,
                    contents: node.contents,
                };
            } else {
                throw new Error('node type not supported');
            }
        },
        storeLocalEntry: (path, entry) => {
            if (FS.isDir(entry['mode'])) {
                FS.mkdirTree(path, entry['mode']);
            } else if (FS.isFile(entry['mode'])) {
                FS.writeFile(path, entry['contents'], { canOwn: true });
            } else {
                throw new Error('node type not supported');
            }

            FS.chmod(path, entry['mode']);
            FS.utime(path, entry['timestamp'], entry['timestamp']);
        },
        removeLocalEntry: (path) => {
            var stat = FS.stat(path);

            if (FS.isDir(stat.mode)) {
                FS.rmdir(path);
            } else if (FS.isFile(stat.mode)) {
                FS.unlink(path);
            }
        },
        loadRemoteEntry: async (handle) => {
            if (handle.kind === 'file') {
                const file = await handle.getFile();
                return {
                    contents: new Uint8Array(await file.arrayBuffer()),
                    mode: nativeFSAsync.FILE_MODE,
                    timestamp: file.lastModifiedDate,
                };
            } else if (handle.kind === 'directory') {
                return {
                    mode: nativeFSAsync.DIR_MODE,
                    timestamp: new Date(),
                };
            } else {
                throw new Error('unknown kind: ' + handle.kind);
            }
        },
        storeRemoteEntry: async (handles, path, entry) => {
            const parentDirHandle = handles.get(PATH.dirname(path));
            const handle = FS.isFile(entry.mode)
                ? await parentDirHandle.getFileHandle(PATH.basename(path), {
                    create: true,
                })
                : await parentDirHandle.getDirectoryHandle(PATH.basename(path), {
                    create: true,
                });
            if (handle.kind === 'file') {
                const writable = await handle.createWritable();
                await writable.write(entry.contents);
                await writable.close();
            }
            handles.set(path, handle);
        },
        removeRemoteEntry: async (handles, path) => {
            const parentDirHandle = handles.get(PATH.dirname(path));
            await parentDirHandle.removeEntry(PATH.basename(path));
            handles.delete(path);
        },
        reconcile: async (mount, src, dst) => {
            let total = 0;

            const create = [];
            Object.keys(src.entries).forEach(function (key) {
                const e = src.entries[key];
                const e2 = dst.entries[key];
                if (
                    !e2 ||
                    (FS.isFile(e.mode) &&
                        e['timestamp'].getTime() > e2['timestamp'].getTime())
                ) {
                    create.push(key);
                    total++;
                }
            });
            // sort paths in ascending order so directory entries are created
            // before the files inside them
            create.sort();

            const remove = [];
            Object.keys(dst.entries).forEach(function (key) {
                if (!src.entries[key]) {
                    remove.push(key);
                    total++;
                }
            });
            // sort paths in descending order so files are deleted before their
            // parent directories
            remove.sort().reverse();

            if (!total) {
                return;
            }

            const handles = src.type === 'remote' ? src.handles : dst.handles;

            for (const path of create) {
                const relPath = PATH.normalize(
                    path.replace(mount.mountpoint, '/'),
                ).substring(1);
                if (dst.type === 'local') {
                    const handle = handles.get(relPath);
                    const entry = await nativeFSAsync.loadRemoteEntry(handle);
                    nativeFSAsync.storeLocalEntry(path, entry);
                } else {
                    const entry = nativeFSAsync.loadLocalEntry(path);
                    await nativeFSAsync.storeRemoteEntry(handles, relPath, entry);
                }
            }

            for (const path of remove) {
                if (dst.type === 'local') {
                    nativeFSAsync.removeLocalEntry(path);
                } else {
                    const relPath = PATH.normalize(
                        path.replace(mount.mountpoint, '/'),
                    ).substring(1);
                    await nativeFSAsync.removeRemoteEntry(handles, relPath);
                }
            }
        },
    };

    module.FS.filesystems.NATIVEFS_ASYNC = nativeFSAsync;

    function ensureMountPathExists(path) {
        if (FS.mkdirTree) FS.mkdirTree(path);
        else mkdirTree(FS, path);

        const { node } = FS.lookupPath(path, {
            follow_mount: false,
        });

        if (FS.isMountpoint(node)) {
            throw new Error(`path '${path}' is already a file system mount point`);
        }
        if (!FS.isDir(node.mode)) {
            throw new Error(`path '${path}' points to a file not a directory`);
        }
        // eslint-disable-next-line
        for (const _ in node.contents) {
            throw new Error(`directory '${path}' is not empty`);
        }
    }

    return async function mountNativeFS(path, fileSystemHandle) {
        if (fileSystemHandle.constructor.name !== 'FileSystemDirectoryHandle') {
            throw new TypeError(
              'Expected argument \'fileSystemHandle\' to be a FileSystemDirectoryHandle',
            );
        }
        ensureMountPathExists(path);
      
        FS.mount(
            FS.filesystems.NATIVEFS_ASYNC,
            { fileSystemHandle },
            path,
        );

        // sync native ==> browser
        await syncfs(FS, true);

        return {
            // sync browser ==> native
            syncfs: async () => await syncfs(FS, false),
        };
    };
}

const getFsHandles = async (dirHandle) => {
    const handles = [];

    async function collect(curDirHandle) {
        for await (const entry of curDirHandle.values()) {
            handles.push(entry);
            if (entry.kind === 'directory') {
                await collect(entry);
            }
        }
    }

    await collect(dirHandle);

    const result = new Map();
    result.set('.', dirHandle);
    for (const handle of handles) {
        const relativePath = (await dirHandle.resolve(handle)).join('/');
        result.set(relativePath, handle);
    }
    return result;
};

const type$4 = 'micropython';

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const mkdir = (FS, path) => {
    try {
        FS.mkdir(path);
    }
    // eslint-disable-next-line no-unused-vars
    catch (_) {
        // ignore as there's no path.exists here
    }
};

const progress$1 = createProgress('mpy');

var micropython = {
    type: type$4,
    module: (version = '1.25.0') =>
        `https://cdn.jsdelivr.net/npm/@micropython/micropython-webassembly-pyscript@${version}/micropython.mjs`,
    async engine({ loadMicroPython }, config, url, baseURL) {
        const { stderr, stdout, get } = stdio({
            stderr: buffered(console.error),
            stdout: buffered(console.log),
        });
        url = url.replace(/\.m?js$/, '.wasm');
        progress$1('Loading MicroPython');
        const interpreter = await get(loadMicroPython({ linebuffer: false, stderr, stdout, url }));
        const py_imports = importPackages$1.bind(this, interpreter, baseURL);
        loader.set(interpreter, py_imports);
        await loadProgress(this, progress$1, interpreter, config, baseURL);
        // Install Micropython Package
        this.writeFile(interpreter, './mip.py', mip);
        if (config.packages) {
            progress$1('Loading packages');
            await py_imports(config.packages.map(fixedRelative, baseURL));
            progress$1('Loaded packages');
        }
        progress$1('Loaded MicroPython');
        if (!interpreter.mountNativeFS)
            interpreter.mountNativeFS = initializeNativeFS(interpreter._module);
        return interpreter;
    },
    registerJSModule,
    run: run$1,
    runAsync,
    runEvent: runEvent$1,
    transform: (interpreter, value) => interpreter.PyProxy.toJs(value),
    writeFile: (interpreter, path, buffer, url) => {
        const { FS, _module: { PATH, PATH_FS } } = interpreter;
        const fs = { FS, PATH, PATH_FS };
        const format = getFormat(path, url);
        if (format) {
            const extractDir = path.slice(0, -1);
            if (extractDir !== './') FS.mkdir(extractDir);
            switch (format) {
                case 'whl':
                case 'zip': {
                    const blob = new Blob([buffer], { type: 'application/zip' });
                    return zip().then(async ({ BlobReader, Uint8ArrayWriter, ZipReader }) => {
                        const zipFileReader = new BlobReader(blob);
                        const zipReader = new ZipReader(zipFileReader);
                        for (const entry of await zipReader.getEntries()) {
                            const { directory, filename } = entry;
                            const name = extractDir + filename;
                            if (directory) mkdir(FS, name);
                            else {
                                mkdir(FS, PATH.dirname(name));
                                const buffer = await entry.getData(new Uint8ArrayWriter);
                                FS.writeFile(name, buffer, {
                                    canOwn: true,
                                });
                            }
                        }
                        zipReader.close();
                    });
                }
                case 'tgz':
                case 'tar.gz': {
                    const TMP = './_.tar.gz';
                    writeFile(fs, TMP, buffer);
                    interpreter.runPython(`
                        import os, gzip, tarfile
                        tar = tarfile.TarFile(fileobj=gzip.GzipFile(fileobj=open("${TMP}", "rb")))
                        for f in tar:
                            name = f"${extractDir}{f.name}"
                            if f.type == tarfile.DIRTYPE:
                                if f.name != "./":
                                    os.mkdir(name.strip("/"))
                            else:
                                dir = os.path.dirname(name)
                                if not os.path.exists(dir):
                                    os.mkdir(dir)
                                source = tar.extractfile(f)
                                with open(name, "wb") as dest:
                                    dest.write(source.read())
                                    dest.close()
                        tar.close()
                        os.remove("${TMP}")
                    `);
                    return;
                }
            }
        }
        return writeFile(fs, path, buffer);
    },
};

async function importPackages$1(interpreter, baseURL, packages) {
    let mip;
    for (const mpyPackage of packages) {
        if (mpyPackage.endsWith('.whl')) {
            const url = absoluteURL(mpyPackage, baseURL);
            const buffer = await fetch$1(url).arrayBuffer();
            await this.writeFile(interpreter, './*', buffer, url);
        }
        else {
            if (!mip) mip = interpreter.pyimport('mip');
            mip.install(mpyPackage);
        }
    }
}
/* c8 ignore stop */

const type$3 = 'pyodide';
const toJsOptions = { dict_converter: Object.fromEntries };

const { stringify } = JSON;

const { apply } = Reflect;
const FunctionPrototype = Function.prototype;

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const overrideMethod = method => function (...args) {
    return apply(method, this, args);
};

let pyproxy, to_js;
const override = intercept => {

    const proxies = new WeakMap;

    const patch = args => {
        for (let arg, i = 0; i < args.length; i++) {
            switch (typeof(arg = args[i])) {
                case 'object':
                    if (arg === null) break;
                    // falls through
                case 'function': {
                    if (pyproxy in arg && !arg[pyproxy].shared?.gcRegistered) {
                        intercept = false;
                        let proxy = proxies.get(arg)?.deref();
                        if (!proxy) {
                            proxy = to_js(arg);
                            const wr = new WeakRef(proxy);
                            proxies.set(arg, wr);
                            proxies.set(proxy, wr);
                        }
                        args[i] = proxy;
                        intercept = true;
                    }
                    break;
                }
            }
        }
    };

    // the patch
    Object.defineProperties(FunctionPrototype, {
        apply: {
            value(context, args) {
                if (intercept) patch(args);
                return apply(this, context, args);
            }
        },
        call: {
            value(context, ...args) {
                if (intercept) patch(args);
                return apply(this, context, args);
            }
        }
    });
};

const progress = createProgress('py');
const indexURLs = new WeakMap();

var pyodide = {
    type: type$3,
    module: (version = '0.27.7') =>
        `https://cdn.jsdelivr.net/pyodide/v${version}/full/pyodide.mjs`,
    async engine({ loadPyodide, version }, config, url, baseURL) {
        progress('Loading Pyodide');
        let { packages, index_urls } = config;
        if (packages) packages = packages.map(fixedRelative, baseURL);
        progress('Loading Storage');
        const indexURL = url.slice(0, url.lastIndexOf('/'));
        // each pyodide version shares its own cache
        const storage = new IDBMapSync(`${indexURL}@${version}`);
        const options = { indexURL };
        const save = config.packages_cache !== 'never';
        await storage.sync();
        // packages_cache = 'never' means: erase the whole DB
        if (!save) storage.clear();
        // otherwise check if cache is known
        else if (packages) {
            // packages_cache = 'passthrough' means: do not use micropip.install
            if (config.packages_cache === 'passthrough') {
                options.packages = packages;
                packages = null;
                storage.clear();
            }
            else {
                packages = packages.sort();
                // packages are uniquely stored as JSON key
                const key = stringify(packages);
                if (storage.has(key)) {
                    const blob = new Blob(
                        [storage.get(key)],
                        { type: 'application/json' },
                    );
                    // this should be used to bootstrap loadPyodide
                    options.lockFileURL = URL.createObjectURL(blob);
                    // versions are not currently understood by pyodide when
                    // a lockFileURL is used instead of micropip.install(packages)
                    // https://github.com/pyodide/pyodide/issues/5135#issuecomment-2441038644
                    // https://github.com/pyscript/pyscript/issues/2245
                    options.packages = packages.map(name => name.split(/[>=<]=/)[0]);
                    packages = null;
                }
            }
        }
        progress('Loaded Storage');
        const { stderr, stdout, get } = stdio();
        const interpreter = await get(
            loadPyodide({ stderr, stdout, ...options }),
        );
        if (config.debug) interpreter.setDebug(true);
        const py_imports = importPackages.bind(interpreter);
        if (index_urls) indexURLs.set(interpreter, index_urls);
        loader.set(interpreter, py_imports);
        await loadProgress(this, progress, interpreter, config, baseURL);
        // if cache wasn't know, import and freeze it for the next time
        if (packages) await py_imports(packages, storage, save);
        await storage.close();
        if (options.lockFileURL) URL.revokeObjectURL(options.lockFileURL);
        progress('Loaded Pyodide');
        if (config.experimental_create_proxy === 'auto') {
            interpreter.runPython([
                'import js',
                'from pyodide.ffi import to_js',
                'o=js.Object.fromEntries',
                'js.experimental_create_proxy=lambda r:to_js(r,dict_converter=o)'
            ].join(';'), { globals: interpreter.toPy({}) });
            to_js = globalThis.experimental_create_proxy;
            delete globalThis.experimental_create_proxy;
            [pyproxy] = Reflect.ownKeys(to_js).filter(
                k => (
                    typeof k === 'symbol' &&
                    String(k) === 'Symbol(pyproxy.attrs)'
                )
            );
            override(true);
        }
        return interpreter;
    },
    registerJSModule,
    run: overrideMethod(run$1),
    runAsync: overrideMethod(runAsync),
    runEvent: overrideMethod(runEvent$1),
    transform: (interpreter, value) => apply(transform$1, interpreter, [value]),
    writeFile: (interpreter, path, buffer, url) => {
        const format = getFormat(path, url);
        if (format) {
            return interpreter.unpackArchive(buffer, format, {
                extractDir: path.slice(0, -1)
            });
        }
        const { FS, PATH, _module: { PATH_FS } } = interpreter;
        return writeFile({ FS, PATH, PATH_FS }, path, buffer);
    },
};

function transform$1(value) {
    const { ffi: { PyProxy } } = this;
    if (value && typeof value === 'object') {
        if (value instanceof PyProxy) return value.toJs(toJsOptions);
        // I believe this case is for LiteralMap which is not a PyProxy
        // and yet it needs to be re-converted to something useful.
        if (value instanceof Map) return new Map([...value.entries()]);
        if (isArray(value)) return value.map(transform$1, this);
    }
    return value;
}

// exposed utility to import packages via polyscript.lazy_py_modules
async function importPackages(packages, storage, save = false) {
    // temporary patch/fix console.log which is used
    // not only by Pyodide but by micropip too and there's
    // no way to intercept those calls otherwise
    const { log } = console;
    const _log = (detail, ...rest) => {
        log(detail, ...rest);
        console.log = log;
        progress(detail);
        console.log = _log;
    };
    console.log = _log;
    await this.loadPackage('micropip');
    const micropip = this.pyimport('micropip');
    if (indexURLs.has(this)) micropip.set_index_urls(indexURLs.get(this));
    await micropip.install(packages, { keep_going: true });
    console.log = log;
    if (save && (storage instanceof IDBMapSync)) {
        const frozen = micropip.freeze();
        storage.set(stringify(packages), frozen);
    }
    micropip.destroy();
}
/* c8 ignore stop */

const type$2 = 'ruby-wasm-wasi';
const jsType = type$2.replace(/\W+/g, '_');

// MISSING:
//  * there is no VFS apparently or I couldn't reach any
//  * I've no idea how to override the stderr and stdout
//  * I've no idea how to import packages

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
var ruby_wasm_wasi = {
    type: type$2,
    experimental: true,
    module: (version = '2.7.1') =>
        `https://cdn.jsdelivr.net/npm/@ruby/3.2-wasm-wasi@${version}/dist/browser/+esm`,
    async engine({ DefaultRubyVM }, config, url, baseURL) {
        url = url.replace(/\/browser\/\+esm$/, '/ruby.wasm');
        const buffer = await fetch$1(url).arrayBuffer();
        const module = await WebAssembly.compile(buffer);
        const { vm: interpreter } = await DefaultRubyVM(module);
        if (config.files) await fetchFiles(this, interpreter, config.files, baseURL);
        if (config.fetch) await fetchPaths(this, interpreter, config.fetch, baseURL);
        if (config.js_modules) await fetchJSModules(config.js_modules, baseURL);
        return interpreter;
    },
    // Fallback to globally defined module fields (i.e. $xworker)
    registerJSModule(interpreter, name, value) {
        name = name.replace(/\W+/g, '__');
        const id = `__module_${jsType}_${name}`;
        globalThis[id] = value;
        this.run(interpreter, `require "js";$${name}=JS.global[:${id}]`);
        delete globalThis[id];
    },
    run: (interpreter, code, ...args) => interpreter.eval(dedent(code), ...args),
    runAsync: (interpreter, code, ...args) => interpreter.evalAsync(dedent(code), ...args),
    async runEvent(interpreter, code, event) {
        // patch common xworker.onmessage/onerror cases
        if (/^xworker\.(on\w+)$/.test(code)) {
            const { $1: name } = RegExp;
            const id = `__module_${jsType}_event`;
            globalThis[id] = event;
            this.run(
                interpreter,
                `require "js";$xworker.call("${name}",JS.global[:${id}])`,
            );
            delete globalThis[id];
        } else {
            // Experimental: allows only events by fully qualified method name
            const method = this.run(interpreter, `method(:${code})`);
            await method.call(code, interpreter.wrap(event));
        }
    },
    transform: (_, value) => value,
    writeFile: () => {
        throw new Error(`writeFile is not supported in ${type$2}`);
    },
};
/* c8 ignore stop */

const type$1 = 'wasmoon';

// MISSING:
//  * I've no idea how to import packages

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
var wasmoon = {
    type: type$1,
    module: (version = '1.16.0') =>
        `https://cdn.jsdelivr.net/npm/wasmoon@${version}/+esm`,
    async engine({ LuaFactory, LuaLibraries }, config, _, baseURL) {
        const { stderr, stdout, get } = stdio();
        const interpreter = await get(new LuaFactory().createEngine());
        interpreter.global.getTable(LuaLibraries.Base, (index) => {
            interpreter.global.setField(index, 'print', stdout);
            interpreter.global.setField(index, 'printErr', stderr);
        });
        if (config.files) await fetchFiles(this, interpreter, config.files, baseURL);
        if (config.fetch) await fetchPaths(this, interpreter, config.fetch, baseURL);
        if (config.js_modules) await fetchJSModules(config.js_modules, baseURL);
        return interpreter;
    },
    // Fallback to globally defined module fields
    registerJSModule: (interpreter, name, value) => {
        interpreter.global.set(name, value);
    },
    run: (interpreter, code, ...args) => {
        try {
            return interpreter.doStringSync(dedent(code), ...args);
        }
        catch (error) {
            io.get(interpreter).stderr(error);
        }
    },
    runAsync: async (interpreter, code, ...args) => {
        try {
            return await interpreter.doString(dedent(code), ...args);
        }
        catch (error) {
            io.get(interpreter).stderr(error);
        }
    },
    runEvent: async (interpreter, code, event) => {
        // allows method(event) as well as namespace.method(event)
        // it does not allow fancy brackets names for now
        const [name, ...keys] = code.split('.');
        let target = interpreter.global.get(name);
        let context;
        for (const key of keys) [context, target] = [target, target[key]];
        try {
            await target.call(context, event);
        }
        catch (error) {
            io.get(interpreter).stderr(error);
        }
    },
    transform: (_, value) => value,
    writeFile: (
        {
            cmodule: {
                module: { FS },
            },
        },
        path,
        buffer,
    ) => writeFileShim(FS, path, buffer),
};
/* c8 ignore stop */

const type = 'webr';
const r = new WeakMap();

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const run = async (interpreter, code) => {
  const { shelter, destroy, io } = r.get(interpreter);
  const { output, result } = await shelter.captureR(dedent(code));
  for (const { type, data } of output) io[type](data);
  // this is a double proxy but it's OK as the consumer
  // of the result here needs to invoke explicitly a conversion
  // or trust the `(await p.toJs()).values` returns what's expected.
  return create$2(result, destroy, { token: false });
};

var webr = {
    type,
    experimental: true,
    module: (version = '0.4.4') =>
        `https://cdn.jsdelivr.net/npm/webr@${version}/dist/webr.mjs`,
    async engine(module, config, _, baseURL) {
        const { get } = stdio();
        const interpreter = new module.WebR();
        await get(interpreter.init().then(() => interpreter));
        const shelter = await new interpreter.Shelter();
        r.set(interpreter, {
          module,
          shelter,
          destroy: shelter.destroy.bind(shelter),
          io: io.get(interpreter),
        });
        if (config.files) await fetchFiles(this, interpreter, config.files, baseURL);
        if (config.fetch) await fetchPaths(this, interpreter, config.fetch, baseURL);
        if (config.js_modules) await fetchJSModules(config.js_modules, baseURL);
        return interpreter;
    },
    // Fallback to globally defined module fields (i.e. $xworker)
    registerJSModule(_, name) {
        console.warn(`Experimental interpreter: module ${name} is not supported (yet)`);
        // TODO: as complex JS objects / modules are not allowed
        // it's not clear how we can bind anything or import a module
        // in a context that doesn't understand methods from JS
        // https://docs.r-wasm.org/webr/latest/convert-js-to-r.html#constructing-r-objects-from-javascript-objects
    },
    run,
    runAsync: run,
    async runEvent(interpreter, code, event) {
        // TODO: WebR cannot convert exoteric objects or any literal
        // to an easy to reason about data/frame ... that conversion
        // is reserved for the future:
        // https://docs.r-wasm.org/webr/latest/convert-js-to-r.html#constructing-r-objects-from-javascript-objects
        await interpreter.evalRVoid(`${code}(event)`, {
          env: { event: { type: [ event.type ] } }
        });
    },
    transform: (_, value) => {
        console.log('transforming', value);
        return value;
    },
    writeFile: () => {
        // MAYBE ???
    },
};
/* c8 ignore stop */

// ⚠️ Part of this file is automatically generated
//    The :RUNTIMES comment is a delimiter and no code should be written/changed after
//    See rollup/build_interpreters.cjs to know more

/** @type {Map<string, object>} */
const registry = new Map();

/** @type {Map<string, object>} */
const configs = new Map();

/* c8 ignore start */
const interpreter$1 = new Proxy(new Map(), {
    get(map, id) {
        if (!map.has(id)) {
            const [type, ...rest] = id.split('@');
            const interpreter = registry.get(type);
            const url = /^(?:\.?\.?\/|[a-z0-9-]+:\/\/)/i.test(rest)
                ? rest.join('@')
                : interpreter.module(...rest);
            map.set(id, {
                url,
                module: import(/* webpackIgnore: true */url),
                engine: interpreter.engine.bind(interpreter),
            });
        }
        const { url, module, engine } = map.get(id);
        return (config, baseURL) =>
            module.then((module) => {
                configs.set(id, config);
                return engine(module, config, url, baseURL);
            });
    },
});
/* c8 ignore stop */

const register = (interpreter) => {
    for (const type of [].concat(interpreter.type)) {
        registry.set(type, interpreter);
    }
};
for (const interpreter of [dummy, micropython, pyodide, ruby_wasm_wasi, wasmoon, webr])
    register(interpreter);

const { parse } = JSON;

// REQUIRES INTEGRATION TEST
/* c8 ignore start */
const getConfigURLAndType = (config, configURL = './config.txt') => {
    let type = typeof config;
    if (type === 'string' && /\.(json|toml|txt)$/.test(config))
        type = RegExp.$1;
    else
        config = configURL;
    return [absoluteURL(config), type];
};

const resolveConfig = (config, configURL, options = {}) => {
    const [absolute, type] = getConfigURLAndType(config, configURL);
    if (type === 'json') {
        options = fetch$1(absolute).json();
    } else if (type === 'toml') {
        options = fetch$1(absolute).text().then(toml);
    } else if (type === 'string') {
        options = parseString(config);
    } else if (type === 'object' && config) {
        options = config;
    } else if (type === 'txt' && typeof options === 'string') {
        options = parseString(options);
    }
    config = absolute;
    return [options, config];
};

const parseString = config => {
    try {
        return parse(config);
    }
    // eslint-disable-next-line no-unused-vars
    catch (_) {
        return toml(config);
    }
};
/* c8 ignore stop */

/**
 * Parse a generic config if it came from an attribute either as URL
 * or as a serialized string. In XWorker case, accepts a pre-defined
 * options to use as it is to avoid needing at all a fetch operation.
 * In latter case, config will be suffixed as `config.txt`.
 * @param {string} id the interpreter name @ version identifier
 * @param {string | object} config optional config file to parse
 * @param {string} [configURL] optional config URL if config is not string
 * @param {object} [options] optional options used to bootstrap XWorker
 * @returns
 */
const getRuntime = (id, config, configURL, options = {}) => {
    if (config) {
        // REQUIRES INTEGRATION TEST
        /* c8 ignore start */
        [options, config] = resolveConfig(config, configURL, options);
        /* c8 ignore stop */
    }
    return resolve$1(options).then(options => interpreter$1[id](options, config));
};

/**
 * @param {string} type the interpreter type
 * @param {string} [version] the optional interpreter version
 * @returns
 */
const getRuntimeID = (type, version = '') =>
    `${type}@${version}`.replace(/@$/, '');

const beforeRun = 'BeforeRun';
const afterRun = 'AfterRun';

const code = [
    `code${beforeRun}`,
    `code${beforeRun}Async`,
    `code${afterRun}`,
    `code${afterRun}Async`,
];

const js = [
    'onWorker',
    'onReady',
    `on${beforeRun}`,
    `on${beforeRun}Async`,
    `on${afterRun}`,
    `on${afterRun}Async`,
];

/* c8 ignore start */
// create a copy of the resolved wrapper with the original
// run and runAsync so that, if used within onBeforeRun/Async
// or onAfterRun/Async polluted entries won't matter and just
// the native utilities will be available without seppuku.
// The same applies if called within `onReady` worker hook.
function patch(resolved, interpreter) {
    const { run, runAsync } = registry.get(this.type);
    return {
        ...resolved,
        run: run.bind(this, interpreter),
        runAsync: runAsync.bind(this, interpreter)
    };
}

/**
 * Created the wrapper to pass along hooked callbacks.
 * @param {object} module the details module
 * @param {object} ref the node or reference to pass as second argument
 * @param {boolean} isAsync if run should be async
 * @param {function?} before callback to run before
 * @param {function?} after callback to run after
 * @returns {object}
 */
const polluteJS = (module, resolved, ref, isAsync, before, after) => {
    if (before || after) {
        const patched = patch.bind(module, resolved);
        const name = isAsync ? 'runAsync' : 'run';
        const method = module[name];
        module[name] = isAsync ?
            async function (interpreter, code, ...args) {
                if (before) await before.call(this, patched(interpreter), ref);
                const result = await method.call(
                    this,
                    interpreter,
                    code,
                    ...args
                );
                if (after) await after.call(this, patched(interpreter), ref);
                return result;
            } :
            function (interpreter, code, ...args) {
                if (before) before.call(this, patched(interpreter), ref);
                const result = method.call(this, interpreter, code, ...args);
                if (after) after.call(this, patched(interpreter), ref);
                return result;
            }
        ;
    }
};
/* c8 ignore stop */

// ⚠️ This file is used to generate xworker.js
//    That means if any import is circular or brings in too much
//    that would be a higher payload for every worker.
//    Please check via `npm run size` that worker code is not much
//    bigger than it used to be before any changes is applied to this file.


let interpreter, runEvent, transform;
const add = (type, fn) => {
    addEventListener(
        type,
        fn ||
            (async (event) => {
                try {
                    await interpreter;
                    runEvent(`xworker.on${type}`, event);
                } catch (error) {
                    postMessage(error);
                }
            }),
        !!fn && { once: true },
    );
};

const {
    proxy: sync,
    native,
    window,
    isWindowProxy
} = await coincident({
    decoder: E,
    transfer: false,
    transform: value => transform ? transform(value) : value
});

const xworker = {
    // propagate the fact SharedArrayBuffer is polyfilled
    polyfill: !native,
    // allows synchronous utilities between this worker and the main thread
    sync,
    // allow access to the main thread world whenever it's possible
    window: native ? window : null,
    // allow introspection for foreign (main thread) refrences
    isWindowProxy,
    // standard worker related events / features
    onmessage: console.info,
    onerror: console.error,
    onmessageerror: console.warn,
    postMessage: postMessage.bind(self),
};

add('message', ({ data: { options, config: baseURL, configURL, code: code$1, hooks } }) => {
    interpreter = (async () => {
        try {
            const { id, tag, type, custom, version, config, async: isAsync } = options;

            const runtimeID = getRuntimeID(type, version);

            const interpreter = await getRuntime(runtimeID, baseURL, configURL, config);

            const { js_modules } = configs.get(runtimeID);

            const mainModules = js_modules?.main;

            const details = create(registry.get(type));

            const resolved = createResolved(
                details,
                custom || type,
                config || {},
                interpreter
            );

            let name = 'run';
            if (isAsync) name += 'Async';

            if (hooks) {
                let before = '';
                let after = '';

                for (const key of code) {
                    const value = hooks[key];
                    if (value) {
                        const asyncCode = key.endsWith('Async');
                        // either async hook and this worker is async
                        // or sync hook and this worker is sync
                        // other shared options possible cases are ignored
                        if ((asyncCode && isAsync) || (!asyncCode && !isAsync)) {
                            if (key.startsWith('codeBefore'))
                                before = value;
                            else
                                after = value;
                        }
                    }
                }

                if (before || after)
                    createOverload(details, name, before, after);

                let beforeCB, afterCB;
                // exclude onWorker and onReady
                for (const key of js.slice(2)) {
                    const value = hooks[key];
                    if (value) {
                        const asyncCode = key.endsWith('Async');
                        if ((asyncCode && isAsync) || (!asyncCode && !isAsync)) {
                            const cb = createFunction(value);
                            if (key.startsWith('onBefore'))
                                beforeCB = cb;
                            else
                                afterCB = cb;
                        }
                    }
                }
                polluteJS(details, resolved, xworker, isAsync, beforeCB, afterCB);
            }

            // there's no way to query the DOM, use foreign CustomEvent and so on
            // in case there's no SharedArrayBuffer around.
            let CustomEvent, document, notify, currentScript = null, target = '';
            if (native) {
                ({ CustomEvent, document } = window);
                currentScript = id && document.getElementById(id) || null;
                notify = kind => dispatch(currentScript, custom || type, kind, true, CustomEvent);
            }

            // TODO: even this is problematic without SharedArrayBuffer
            // but let's see if we can manage to make it work somehow.
            const JSModules = createJSModules(window, sync, mainModules, baseURL);

            registerJSModules(type, details, interpreter, JSModules);
            details.registerJSModule(interpreter, 'polyscript', {
                IDBMap,
                IDBMapSync,
                xworker,
                currentScript,
                config: resolved.config,
                js_modules: JSModules,
                get target() {
                    if (!target && currentScript) {
                        if (tag === 'SCRIPT') {
                            currentScript.after(assign(
                                window.document.createElement(`script-${custom || type}`),
                                { id: (target = `${id}-target`) }
                            ));
                        }
                        else {
                            target = id;
                            currentScript.replaceChildren();
                            currentScript.style.display = 'block';
                        }
                    }
                    return target;
                }
            });

            // simplify runEvent calls
            runEvent = details.runEvent.bind(details, interpreter);

            // allows transforming arguments with sync
            transform = details.transform.bind(details, interpreter);

            // notify worker ready to execute
            if (currentScript) notify('ready');

            // evaluate the optional `onReady` callback
            if (hooks?.onReady) {
                createFunction(hooks?.onReady).call(
                    details,
                    patch.call(details, resolved, interpreter),
                    xworker,
                );
            }

            // run either sync or async code in the worker
            await details[name](interpreter, code$1);

            if (['micropython', 'pyodide'].includes(details.type)) {
                // this dance is required due Pyodide issues with runtime sync exports
                // or MicroPython issue with `runPython` not returning values
                const polyscript = 'polyscript';
                const workers = `__${polyscript}_workers__`;
                const exports = '__export__';
                interpreter.runPython([
                    `import js as ${workers}`,
                    `${workers}.${workers} = "${exports}" in locals() and ${exports} or []`,
                    `del ${workers}`,
                ].join('\n'));
                const list = [...globalThis[workers]];
                delete globalThis[workers];
                if (list.length) {
                    interpreter.runPython([
                        `from ${polyscript} import xworker as ${workers}`,
                        ...list.map(util => `${workers}.sync.${util} = ${util}`),
                        `del ${workers}`,
                    ].join('\n'));
                }
            }

            // notify worker done executing
            if (currentScript) notify('done');
            postMessage('polyscript:done');
            return interpreter;
        } catch (error) {
            postMessage(error);
        }
    })();
    add('error');
    add('message');
    add('messageerror');
    if (native) {
        addEventListener('py:progress', ({ type, detail }) => {
            window.dispatchEvent(new window.CustomEvent(type, { detail }));
        });
    }
});
