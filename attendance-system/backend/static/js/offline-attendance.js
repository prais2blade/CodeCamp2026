const ATTENDANCE_QUEUE_KEY = "attendance_queue";
const LAST_SYNC_KEY = "last_sync";
const SYNC_LOG_KEY = "attendance_sync_logs";

/* =========================
   Queue Management
========================= */

function getQueue() {

    return JSON.parse(

        localStorage.getItem(
            ATTENDANCE_QUEUE_KEY
        ) || "[]"

    );

}

function saveQueue(queue) {

    localStorage.setItem(

        ATTENDANCE_QUEUE_KEY,

        JSON.stringify(queue)

    );

}

/* =========================
   Toast Notifications
========================= */

function showToast(message) {

    const toast = document.getElementById(
        "sync-toast"
    );

    if (!toast)
        return;

    toast.innerText = message;

    toast.classList.remove(
        "hidden"
    );

    setTimeout(() => {

        toast.classList.add(
            "hidden"
        );

    }, 3000);

}

/* =========================
   Last Sync
========================= */

function saveLastSync() {

    localStorage.setItem(

        LAST_SYNC_KEY,

        new Date().toLocaleString()

    );

}

function getLastSync() {

    return localStorage.getItem(

        LAST_SYNC_KEY

    ) || "Never";

}

/* =========================
   Queue Attendance
========================= */

function queueAttendance(studentId) {

    const queue = getQueue();

    queue.push({

        student_id: studentId,

        timestamp: new Date().toISOString(),

        synced: false

    });

    saveQueue(queue);

    addLog(

        "Attendance queued for " +

        studentId

    );

    updateQueueCount();

    updateSyncDashboard();

    showToast(
        "Attendance saved offline"
    );

}

/* =========================
   Queue Counter
========================= */

function updateQueueCount() {

    const badge = document.getElementById(
        "offline-count"
    );

    if (!badge)
        return;

    badge.innerText = getQueue().length;

}

/* =========================
   Connection Status
========================= */

function updateConnectionStatus() {

    const badge = document.getElementById(
        "sync-status"
    );

    if (!badge)
        return;

    if (navigator.onLine) {

        badge.innerText =
            "Online";

        badge.className =
            "bg-green-500 text-white px-3 py-1 rounded-full text-sm";

    }

    else {

        badge.innerText =
            "Offline";

        badge.className =
            "bg-yellow-500 text-white px-3 py-1 rounded-full text-sm";

    }

}

/* =========================
   Dashboard Sync Card
========================= */

function updateSyncDashboard() {

    const queueCount =
        getQueue().length;

    const queueElement =
        document.getElementById(
            "sync-dashboard-queue"
        );

    if (queueElement) {

        queueElement.innerText =
            queueCount;

    }

    const syncElement =
        document.getElementById(
            "last-sync"
        );

    if (syncElement) {

        syncElement.innerText =
            getLastSync();

    }

    const statusElement =
        document.getElementById(
            "sync-dashboard-status"
        );

    if (statusElement) {

        statusElement.innerText =
            navigator.onLine
                ? "Online"
                : "Offline";

    }

}

/* =========================
   Sync Queue
========================= */

async function syncQueue() {

    const queue = getQueue();

    if (!queue.length)
        return;

    console.log(
        "Syncing attendance queue..."
    );

    for (const item of queue) {

        try {

            const response = await fetch(

                "/api/attendance/scan/",

                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json",

                        "X-CSRFToken":
                            getCookie(
                                "csrftoken"
                            )

                    },

                    body: JSON.stringify({

                        student_id:
                            item.student_id

                    })

                }

            );

            if (!response.ok) {

                throw new Error(
                    "Sync failed"
                );

            }

        }

        catch (error) {

            console.log(
                "Sync stopped. Still offline."
            );

            return;

        }

    }

    localStorage.removeItem(
        ATTENDANCE_QUEUE_KEY
    );

    saveLastSync();

    addLog(
        "Attendance queue synced successfully"
    );

    updateQueueCount();

    updateSyncDashboard();

    showToast(
        "Attendance queue synced successfully"
    );

    console.log(
        "Attendance queue synced."
    );

}

/* =========================
   Cookie Helper
========================= */

function getCookie(name) {

    let cookieValue = null;

    if (document.cookie &&
        document.cookie !== "") {

        const cookies =
            document.cookie.split(";");

        for (let i = 0; i < cookies.length; i++) {

            const cookie =
                cookies[i].trim();

            if (

                cookie.substring(
                    0,
                    name.length + 1

                ) === (name + "=")

            ) {

                cookieValue =
                    decodeURIComponent(

                        cookie.substring(
                            name.length + 1
                        )

                    );

                break;

            }

        }

    }

    return cookieValue;

}

/* =========================
   Connection Events
========================= */

window.addEventListener(

    "online",

    function () {

        updateConnectionStatus();

        updateSyncDashboard();

        showToast(
            "Internet restored. Syncing attendance..."
        );
        addLog(
            "Internet connection restored"
        );

        syncQueue();

    }

);

window.addEventListener(

    "offline",

    function () {

        updateConnectionStatus();

        updateSyncDashboard();

        showToast(
            "Offline mode active"
        );

        addLog(
            "Offline mode activated"
        );

    }

);

/* =========================
   Automatic Background Sync
========================= */

setInterval(

    function () {

        if (

            navigator.onLine &&

            getQueue().length > 0

        ) {

            syncQueue();

        }

    },

    10000

);

/* =========================
   Startup
========================= */

document.addEventListener(

    "DOMContentLoaded",

    function () {

        updateQueueCount();

        updateConnectionStatus();

        updateSyncDashboard();

        updateLogViewer();

        if (

            navigator.onLine &&

            getQueue().length > 0

        ) {

            syncQueue();

        }

    }

);

function getLogs() {

    return JSON.parse(

        localStorage.getItem(
            SYNC_LOG_KEY
        ) || "[]"

    );

}

function saveLogs(logs) {

    localStorage.setItem(

        SYNC_LOG_KEY,

        JSON.stringify(logs)

    );

}

function addLog(message) {

    const logs = getLogs();

    logs.unshift({

        message: message,

        timestamp:
            new Date().toLocaleString()

    });

    if (logs.length > 100) {

        logs.pop();

    }

    saveLogs(logs);

    updateLogViewer();

}

function updateLogViewer() {

    const container = document.getElementById(
        "sync-log-viewer"
    );

    if (!container)
        return;

    const logs = getLogs();

    container.innerHTML = "";

    logs.forEach(log => {

        const div =
            document.createElement("div");

        div.className =
            "border-b pb-2";

        div.innerHTML = `

            <p class="text-sm">

                ${log.message}

            </p>

            <p class="text-xs text-gray-500">

                ${log.timestamp}

            </p>

        `;

        container.appendChild(div);

    });

}