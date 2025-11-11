// Tooltip initialization
document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips everywhere
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Product card hover effect
    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.querySelector('.card-img-top').style.transform = 'scale(1.05)';
        });
        card.addEventListener('mouseleave', () => {
            card.querySelector('.card-img-top').style.transform = 'scale(1)';
        });
    });
});