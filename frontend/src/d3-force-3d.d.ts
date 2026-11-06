declare module 'd3-force-3d' {
  // Minimal typing for the forces used by NetworkGraph.
  type Accessor<T> = number | ((node: T) => number)
  interface Force<T> {
    (alpha: number): void
    strength(s: Accessor<T>): Force<T>
    radius?(r: Accessor<T>): Force<T>
  }
  export function forceX<T>(x?: number): Force<T>
  export function forceY<T>(y?: number): Force<T>
  export function forceCollide<T>(radius?: Accessor<T>): Force<T>
}
