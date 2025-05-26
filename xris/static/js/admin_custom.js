// admin_custom.js

// 🔵 Rotate logo on hover (optional effect)
document.addEventListener('DOMContentLoaded', function () {
    const logo = document.querySelector('.sidebar-logo img');
    if (logo) {
        logo.addEventListener('mouseover', () => {
            logo.style.transform = 'rotate(5deg)';
        });
        logo.addEventListener('mouseout', () => {
            logo.style.transform = 'rotate(0deg)';
        });
    }

    // 🔥 Force insert favicon
    const faviconUrl = "/static/img/favicon.ico"; // 👈 Your favicon path

    let faviconLink = document.querySelector("link[rel~='icon']");
    if (!faviconLink) {
        faviconLink = document.createElement('link');
        faviconLink.rel = 'icon';
        document.head.appendChild(faviconLink);
    }
    faviconLink.type = "image/x-icon";
    faviconLink.href = faviconUrl;
});
