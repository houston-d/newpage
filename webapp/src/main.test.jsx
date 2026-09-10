import { beforeEach, describe, expect, it, vi } from "vitest";

const renderMock = vi.fn();
const createRootMock = vi.fn(() => ({ render: renderMock }));
const clearCachedSummariesMock = vi.fn();

vi.mock("react-dom/client", () => ({
  default: {
    createRoot: createRootMock,
  },
}));

vi.mock("./services/summaryCache", () => ({
  clearCachedSummaries: clearCachedSummariesMock,
}));

describe("main startup", () => {
  beforeEach(() => {
    vi.resetModules();
    createRootMock.mockClear();
    renderMock.mockClear();
    clearCachedSummariesMock.mockClear();
    document.body.innerHTML = '<div id="root"></div>';
  });

  it("clears cached summaries before rendering the app", async () => {
    await import("./main.jsx");

    expect(clearCachedSummariesMock).toHaveBeenCalledTimes(1);
    expect(createRootMock).toHaveBeenCalledTimes(1);
    expect(renderMock).toHaveBeenCalledTimes(1);
    expect(clearCachedSummariesMock.mock.invocationCallOrder[0]).toBeLessThan(
      createRootMock.mock.invocationCallOrder[0],
    );
  });
});
