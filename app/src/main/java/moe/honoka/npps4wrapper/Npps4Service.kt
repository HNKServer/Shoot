package moe.honoka.npps4wrapper

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.content.pm.ServiceInfo
import android.util.Log
import org.json.JSONObject

class Npps4Service : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: ACTION_START
        val host = intent?.getStringExtra(EXTRA_HOST) ?: "127.0.0.1"
        val port = intent?.getIntExtra(EXTRA_PORT, 51376) ?: 51376
        when (action) {
            ACTION_START -> startAsync(host, port, restart = false)
            ACTION_RESTART -> startAsync(host, port, restart = true)
            ACTION_STOP -> stopAsync()
            else -> startAsync(host, port, restart = false)
        }
        return START_STICKY
    }

    private fun startAsync(host: String, port: Int, restart: Boolean) {
        val label = if (restart) "NPPS4 restarting on $host:$port" else "NPPS4 starting on $host:$port"
        startForegroundSafe(label)
        Thread {
            try {
                if (restart) {
                    updateNotification("NPPS4 stopping old server...")
                    try { PythonBridge.stop(this) } catch (_: Throwable) {}
                    waitUntilStopped(host, port, 5000)
                }
                updateNotification(label)
                FileOps.ensureTemplate(this)
                FileOps.rewriteDefaultConfig(this)
                val result = PythonBridge.start(this, host, port)
                if (!result.optBoolean("ok", false)) {
                    updateNotification("NPPS4 start rejected: ${result.optString("error", "unknown error")}")
                    return@Thread
                }
                monitorStartup(host, port)
            } catch (t: Throwable) {
                Log.e(TAG, "Failed to start NPPS4", t)
                CrashReporter.append(this, "Failed to start NPPS4", t)
                updateNotification("NPPS4 start failed: ${t.javaClass.simpleName}")
            }
        }.start()
    }

    private fun stopAsync() {
        updateNotification("NPPS4 stopping...")
        Thread {
            try {
                PythonBridge.stop(this)
                waitUntilStopped(null, null, 5000)
                updateNotification("NPPS4 stopped")
            } catch (t: Throwable) {
                Log.w(TAG, "Stop requested but server may not be running", t)
                CrashReporter.append(this, "Stop requested but server may not be running", t)
                updateNotification("NPPS4 stop failed: ${t.javaClass.simpleName}")
            }
            try { stopForeground(STOP_FOREGROUND_REMOVE) } catch (_: Throwable) {}
            stopSelf()
        }.start()
    }

    private fun monitorStartup(host: String, port: Int) {
        var lastPhase = "starting"
        repeat(80) {
            val s: JSONObject = try { PythonBridge.safeStatus(this, host, port) } catch (_: Throwable) { JSONObject() }
            val phase = s.optString("phase", "starting")
            val running = s.optBoolean("running", false)
            val tcp = s.optBoolean("tcp_health", false)
            val error = s.optString("last_error", "")
            if (running && tcp) {
                updateNotification("NPPS4 running on $host:$port")
                return
            }
            if (phase == "error") {
                updateNotification("NPPS4 start failed")
                if (error.isNotBlank()) CrashReporter.append(this, "NPPS4 Python state error", RuntimeException(error.take(12000)))
                return
            }
            if (phase != lastPhase) {
                lastPhase = phase
                updateNotification("NPPS4 starting: $phase")
            }
            try { Thread.sleep(500) } catch (_: InterruptedException) { return }
        }
        updateNotification("NPPS4 still starting; open app for status")
    }

    private fun waitUntilStopped(host: String?, port: Int?, timeoutMs: Long) {
        val end = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < end) {
            val s: JSONObject = try {
                if (host != null && port != null) PythonBridge.safeStatus(this, host, port) else PythonBridge.status(this)
            } catch (_: Throwable) { JSONObject() }
            val phase = s.optString("phase", "stopped")
            val threadAlive = s.optBoolean("thread_alive", false)
            val tcp = s.optBoolean("tcp_health", false)
            if (!threadAlive && !tcp && (phase == "stopped" || phase == "idle" || phase == "error" || phase.isBlank())) return
            try { Thread.sleep(200) } catch (_: InterruptedException) { return }
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = getSystemService(NotificationManager::class.java)
            val ch = NotificationChannel(CHANNEL_ID, "NPPS4 Server", NotificationManager.IMPORTANCE_LOW)
            ch.setShowBadge(false)
            nm.createNotificationChannel(ch)
        }
    }

    private fun startForegroundSafe(text: String) {
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIFICATION_ID, notification(text), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            } else {
                startForeground(NOTIFICATION_ID, notification(text))
            }
        } catch (t: Throwable) {
            Log.e(TAG, "startForeground failed", t)
            CrashReporter.append(this, "startForeground failed", t)
        }
    }

    private fun updateNotification(text: String) {
        try {
            val nm = getSystemService(NotificationManager::class.java)
            nm.notify(NOTIFICATION_ID, notification(text))
        } catch (t: Throwable) {
            Log.w(TAG, "notification update failed", t)
        }
    }

    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stopIntent = Intent(this, Npps4Service::class.java).setAction(ACTION_STOP)
        val stop = PendingIntent.getService(
            this, 1, stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("NPPS4 Android Wrapper")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(open)
            .addAction(android.R.drawable.ic_media_pause, "Stop", stop)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setLocalOnly(true)
            .build()
    }

    companion object {
        private const val TAG = "Npps4Service"
        private const val CHANNEL_ID = "npps4_server_status_v2"
        private const val NOTIFICATION_ID = 1
        const val ACTION_START = "moe.honoka.npps4wrapper.START"
        const val ACTION_STOP = "moe.honoka.npps4wrapper.STOP"
        const val ACTION_RESTART = "moe.honoka.npps4wrapper.RESTART"
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"

        fun start(context: Context, host: String, port: Int) {
            val i = Intent(context, Npps4Service::class.java)
                .setAction(ACTION_START)
                .putExtra(EXTRA_HOST, host)
                .putExtra(EXTRA_PORT, port)
            context.startService(i)
        }

        fun restart(context: Context, host: String, port: Int) {
            val i = Intent(context, Npps4Service::class.java)
                .setAction(ACTION_RESTART)
                .putExtra(EXTRA_HOST, host)
                .putExtra(EXTRA_PORT, port)
            context.startService(i)
        }

        fun stop(context: Context) {
            val i = Intent(context, Npps4Service::class.java).setAction(ACTION_STOP)
            context.startService(i)
        }
    }
}
