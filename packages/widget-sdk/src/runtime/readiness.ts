export type Deferred<T> = {
  promise: Promise<T>;
  resolve(value: T): void;
  reject(reason: unknown): void;
  settled: boolean;
};

export function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const deferred: Deferred<T> = {
    promise: new Promise<T>((innerResolve, innerReject) => {
      resolve = innerResolve;
      reject = innerReject;
    }),
    resolve(value: T) {
      if (deferred.settled) return;
      deferred.settled = true;
      resolve(value);
    },
    reject(reason: unknown) {
      if (deferred.settled) return;
      deferred.settled = true;
      reject(reason);
    },
    settled: false,
  };
  return deferred;
}
