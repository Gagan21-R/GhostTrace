import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

// jsdom lacks these browser APIs used by charts, graph and animations.
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver = RO;
(globalThis as any).IntersectionObserver = RO;
Element.prototype.scrollIntoView = () => {};
window.matchMedia = window.matchMedia || ((() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })) as any);
URL.createObjectURL = () => "blob:test";
URL.revokeObjectURL = () => {};
