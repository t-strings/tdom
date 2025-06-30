import sabayon from 'https://cdn.jsdelivr.net/npm/sabayon/dist/polyfill.js';

// ignore browsers that already support SharedArrayBuffer
if (!globalThis.crossOriginIsolated) {
  const { isArray } = Array;
  const isOptions = args => args.length && typeof args[0] === 'object' && args[0] !== null;

  // early patch Blob to inject sabayon polyfill for service-worker
  globalThis.Blob = class extends Blob {
    constructor(blobParts, ...args) {
      if (
        isOptions(args) &&
        args[0].type === 'text/javascript' &&
        isArray(blobParts) &&
        typeof blobParts.at(0) === 'string'
      ) {
        blobParts[0] = blobParts[0].replace(
          /^\/\*@\*\//,
          'import "https://cdn.jsdelivr.net/npm/sabayon/dist/polyfill.js";'
        );
      }
      super(blobParts, ...args);
    }
  };

  // early patch Worker to bootstrap sabayon for service-worker
  globalThis.Worker = class extends Worker {
    constructor(url, ...args) {
      if (isOptions(args)) {
        const sw = args[0].serviceWorker || args[0].service_worker;
        if (sw) sabayon(sw);
      }
      super(url, ...args);
    }
  };
}
