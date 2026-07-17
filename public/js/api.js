(function (global) {
    "use strict";

    var API_BASE = "/api";

    function messageFor(payload, fallback) {
        if (typeof global.formatApiError === "function") {
            return global.formatApiError(payload, fallback);
        }
        return fallback;
    }

    function requestError(response, payload, fallback) {
        var error = new Error(messageFor(payload, fallback));
        error.status = response.status;
        error.payload = payload;
        return error;
    }

    async function request(path, options) {
        var settings = options || {};
        var headers = new Headers(settings.headers || {});
        var requestOptions = {
            method: settings.method || "GET",
            headers: headers,
            credentials: "same-origin"
        };

        if (settings.body !== undefined) {
            headers.set("Content-Type", "application/json");
            requestOptions.body = JSON.stringify(settings.body);
        }

        var response;
        try {
            response = await global.fetch(API_BASE + path, requestOptions);
        } catch (networkError) {
            throw new Error("Unable to connect to the service. Please retry.");
        }

        var payload = null;
        try {
            payload = await response.json();
        } catch (parseError) {
            payload = null;
        }

        if (!response.ok) {
            throw requestError(response, payload, "Request failed. Please retry.");
        }

        return payload;
    }

    async function getCurrentUser() {
        return request("/auth/me");
    }

    async function requireCurrentUser() {
        try {
            return await getCurrentUser();
        } catch (error) {
            if (error.status !== 401) {
                throw error;
            }
        }

        global.location.replace("login.html");
        return null;
    }

    async function logout() {
        try {
            await request("/auth/logout", { method: "POST" });
        } catch (error) {
            if (error.status !== 401) {
                throw error;
            }
        }
    }

    window.blogApi = {
        request: request,
        getCurrentUser: getCurrentUser,
        requireCurrentUser: requireCurrentUser,
        login: function (credentials) {
            return request("/auth/login", { method: "POST", body: credentials });
        },
        logout: logout,
        getPublishedPosts: function () {
            return request("/posts");
        },
        createPost: function (post) {
            return request("/posts", { method: "POST", body: post });
        },
        getMyPosts: function () {
            return request("/posts/mine");
        },
        getPendingPosts: function () {
            return request("/admin/posts?status=pending");
        },
        reviewPost: function (postId, review) {
            return request(`/admin/posts/${postId}/review`, {
                method: "POST",
                body: review
            });
        }
    };
})(window);
