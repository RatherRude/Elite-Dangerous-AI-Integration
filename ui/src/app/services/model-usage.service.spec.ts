import { normalizeTokenUsage } from "./model-usage.service";

describe("token accounting semantics", () => {
    const usage = { input_tokens: 100, cached_tokens: 20, output_tokens: 40, reasoning_tokens: 15, total_tokens: 140 };
    it("does not stack cached or included reasoning tokens twice", () => {
        const normalized = normalizeTokenUsage({ ...usage, reasoning_tokens_in_output: true });
        expect(normalized.liveInputTokens + normalized.cachedTokens + normalized.visibleOutputTokens + normalized.stackedReasoningTokens).toBe(140);
        expect(normalized.reasoningTokens).toBe(15);
    });
    it("preserves separately reported output when reasoning is explicitly excluded", () => {
        const normalized = normalizeTokenUsage({ ...usage, reasoning_tokens_in_output: false });
        expect(normalized.visibleOutputTokens).toBe(40);
        expect(normalized.stackedReasoningTokens).toBe(15);
    });
    it("does not invent an additive breakdown for unknown provider semantics", () => {
        const normalized = normalizeTokenUsage({ ...usage, total_tokens: null });
        expect(normalized.visibleOutputTokens).toBe(40);
        expect(normalized.reasoningTokens).toBe(15);
        expect(normalized.stackedReasoningTokens).toBe(0);
    });
    it("uses reported legacy totals to resolve output accounting and rejects malformed counts", () => {
        expect(normalizeTokenUsage(usage).visibleOutputTokens).toBe(25);
        expect(normalizeTokenUsage({ ...usage, total_tokens: 155 }).effectiveOutputTokens).toBe(55);
        expect(normalizeTokenUsage({ input_tokens: -2, output_tokens: "3", reasoning_tokens: NaN }).outputTokens).toBe(0);
    });
    it("distinguishes unknown usage on failure from a reported zero-token call", () => {
        expect(normalizeTokenUsage({ total_tokens: null }).hasReportedTotal).toBeFalse();
        expect(normalizeTokenUsage({}).hasReportedTotal).toBeFalse();
        expect(normalizeTokenUsage({ total_tokens: 0 }).hasReportedTotal).toBeTrue();
    });
});
