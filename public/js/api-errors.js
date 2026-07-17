(function (global) {
    "use strict";

    var publicRegistrationDetails = [
        "\u672a\u8bf7\u6c42\u9a8c\u8bc1\u7801",
        "\u672a\u8bf7\u6c42\u9a8c\u8bc1\u7801\u3002",
        "\u9a8c\u8bc1\u7801\u5df2\u4f7f\u7528",
        "\u9a8c\u8bc1\u7801\u5df2\u4f7f\u7528\u3002",
        "\u9a8c\u8bc1\u7801\u9519\u8bef",
        "\u9a8c\u8bc1\u7801\u9519\u8bef\u3002",
        "\u9a8c\u8bc1\u7801\u5df2\u8fc7\u671f",
        "\u9a8c\u8bc1\u7801\u5df2\u8fc7\u671f\u3002",
        "\u7528\u6237\u540d\u6216\u90ae\u7bb1\u5df2\u5b58\u5728",
        "\u7528\u6237\u540d\u6216\u90ae\u7bb1\u5df2\u5b58\u5728\u3002"
    ];

    function formatApiError(payload, fallback) {
        const safeFallback = typeof fallback === "string" && fallback.trim()
            ? fallback
            : "请求失败，请稍后重试。";

        if (!payload || typeof payload !== "object") {
            return safeFallback;
        }

        if (typeof payload.detail === "string") {
            return publicRegistrationDetails.indexOf(payload.detail) !== -1
                ? payload.detail
                : safeFallback;
        }

        if (!Array.isArray(payload.detail)) {
            return safeFallback;
        }

        for (const error of payload.detail) {
            if (!error || typeof error !== "object") {
                continue;
            }

            const location = Array.isArray(error.loc) ? error.loc : [];
            const field = location[location.length - 1];

            if (field === "password" && error.type === "string_too_short") {
                const minLength = error.ctx && typeof error.ctx.min_length === "number"
                    ? error.ctx.min_length
                    : 8;
                return `密码长度至少 ${minLength} 位。`;
            }

            if (field === "username" && error.type === "string_pattern_mismatch") {
                return "用户名仅可使用中文、英文、数字、下划线或短横线。";
            }
        }

        return safeFallback;
    }

    global.formatApiError = formatApiError;
})(window);
