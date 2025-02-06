document.addEventListener('DOMContentLoaded', function() {
    // Check backend status
    fetch('http://127.0.0.1:8000/docs')
        .then(response => {
            document.getElementById('status').textContent = 'Connected';
            document.getElementById('status').style.color = '#27ae60';
        })
        .catch(error => {
            document.getElementById('status').textContent = 'Not Connected';
            document.getElementById('status').style.color = '#c0392b';
        });

    // Toggle chat widget
    document.getElementById('toggle').addEventListener('click', function() {
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            chrome.tabs.sendMessage(tabs[0].id, {action: "toggle"});
        });
    });

    // Settings button (placeholder for future features)
    document.getElementById('settings').addEventListener('click', function() {
        alert('Settings feature coming soon!');
    });
});
