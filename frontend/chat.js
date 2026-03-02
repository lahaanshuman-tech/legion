const socket = io({
    withCredentials: true
});

const messagesDiv = document.getElementById("messages");
const input = document.getElementById("msg-input");
const sendBtn = document.getElementById("send-btn");

// Helper: display a message
function displayMessage(msg) {
    const div = document.createElement("div");
    div.classList.add("message");
    const time = new Date(msg.created_at).toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata"
    });
    
    div.innerHTML = `<strong>${msg.username}:</strong> ${msg.text} <small>${time}</small>`;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Fetch chat history on load
async function fetchChatHistory() {
    const res = await fetch("/api/m/chat-hist", {
        credentials: "include"
    });
    const data = await res.json();
    data.messages.forEach(displayMessage);
}
fetchChatHistory();

// Send message on button click
sendBtn.addEventListener("click", () => {
    const text = input.value.trim();
    if (!text) return;
    socket.emit("send_msg", { text });
    input.value = "";
});

// Also send message on Enter key
input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendBtn.click();
});

// Receive message
socket.on("receive_msg", (msg) => {
    displayMessage(msg);
});