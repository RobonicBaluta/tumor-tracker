declare module 'gif.js' {
  interface GIFOptions {
    workers?: number
    quality?: number
    width: number
    height: number
    workerScript?: string
    background?: string
    transparent?: string | null
    repeat?: number
    dither?: boolean | string
    debug?: boolean
  }

  interface AddFrameOptions {
    delay?: number
    copy?: boolean
    dispose?: number
  }

  class GIF {
    constructor(opts: GIFOptions)
    addFrame(
      element: HTMLCanvasElement | HTMLImageElement | CanvasRenderingContext2D | ImageData,
      opts?: AddFrameOptions,
    ): void
    on(event: 'start', cb: () => void): void
    on(event: 'progress', cb: (progress: number) => void): void
    on(event: 'finished', cb: (blob: Blob) => void): void
    on(event: 'abort', cb: () => void): void
    render(): void
    abort(): void
  }

  export default GIF
}

declare module 'gif.js/dist/gif.worker.js?url' {
  const url: string
  export default url
}
