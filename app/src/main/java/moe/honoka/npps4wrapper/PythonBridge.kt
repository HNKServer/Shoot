package moe.honoka.npps4wrapper

import android.content.Context
import android.os.Environment
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File

object PythonBridge {
    @Synchronized
    fun ensure(context: Context): Python {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        return Python.getInstance()
    }

    fun isStarted(): Boolean = Python.isStarted()

    private fun module(context: Context): PyObject = ensure(context).getModule("android_wrapper")

    fun workDir(context: Context): File = File(context.getExternalFilesDir(null), "npps4")
    fun publicBase(context: Context): File {
        val prefs = context.getSharedPreferences("paths", Context.MODE_PRIVATE)
        val saved = prefs.getString("public_base", null)
        return File(saved ?: File(Environment.getExternalStorageDirectory(), "NPPS4").absolutePath)
    }

    /** Save a user-selected CDN ZIP directory without copying files.
     *
     * This is intentionally just the directory containing the CN archive ZIPs.
     * The folder name is not interpreted: it does not have to be list_CN_Android.
     */
    fun setPublicBase(context: Context, dir: File) {
        context.getSharedPreferences("paths", Context.MODE_PRIVATE)
            .edit().putString("public_base", dir.absolutePath).apply()
    }
    fun configFile(context: Context): File = File(workDir(context), "config.toml")

    private fun hasZipFiles(dir: File): Boolean = try {
        dir.isDirectory && (dir.listFiles { f -> f.isFile && f.name.endsWith(".zip", ignoreCase = true) }?.isNotEmpty() == true)
    } catch (_: Throwable) { false }

    private fun hasDbFiles(dir: File): Boolean = try {
        dir.isDirectory && (dir.listFiles { f -> f.isFile && (f.name.endsWith(".db_", ignoreCase = true) || f.name.endsWith(".db", ignoreCase = true)) }?.isNotEmpty() == true)
    } catch (_: Throwable) { false }

    fun cnAndroidArchives(context: Context): File = publicBase(context)

    fun dbRoot(context: Context): File {
        // Always prefer generated/bundled honoka CN master data. This is small
        // server-side master data, not the 10+ GB client CDN mirror.
        val generated = File(workDir(context), "data/db_cn_honoka")
        return generated
    }
    fun exportsDir(context: Context): File = File(workDir(context), "exports")
    fun serverDataFile(context: Context): File = File(workDir(context), "npps4/server_data.json")

    fun prepare(context: Context): JSONObject {
        val result = module(context).callAttr(
            "prepare_workspace",
            workDir(context).absolutePath,
            configFile(context).absolutePath,
            cnAndroidArchives(context).absolutePath,
            dbRoot(context).absolutePath
        ).toString()
        return JSONObject(result)
    }

    fun extractMasterDb(context: Context): JSONObject {
        prepare(context)
        val outDir = File(workDir(context), "data/db_cn_honoka")
        val result = module(context).callAttr(
            "generate_honoka_master_dbs",
            workDir(context).absolutePath,
            configFile(context).absolutePath,
            outDir.absolutePath
        ).toString()
        // Make future config rewrites and starts prefer the generated DB root.
        val cfg = configFile(context)
        if (cfg.exists()) {
            cfg.writeText(cfg.readText(Charsets.UTF_8).replace(Regex("db_root = \"[^\"]*\""), "db_root = \"${outDir.absolutePath.replace('\\', '/')}\""), Charsets.UTF_8)
        }
        return JSONObject(result)
    }

    fun start(context: Context, host: String, port: Int): JSONObject {
        prepare(context)
        val result = module(context).callAttr(
            "start",
            workDir(context).absolutePath,
            configFile(context).absolutePath,
            host,
            port,
            cnAndroidArchives(context).absolutePath,
            dbRoot(context).absolutePath
        ).toString()
        return JSONObject(result)
    }

    fun stop(context: Context): JSONObject {
        if (!Python.isStarted()) return JSONObject(mapOf("ok" to false, "error" to "Python runtime not started"))
        val result = module(context).callAttr("stop").toString()
        return JSONObject(result)
    }

    fun status(context: Context): JSONObject {
        val result = module(context).callAttr("status").toString()
        return JSONObject(result)
    }

    fun reloadEditableData(context: Context): JSONObject {
        prepare(context)
        val result = module(context).callAttr(
            "reload_editable_data",
            workDir(context).absolutePath,
            configFile(context).absolutePath
        ).toString()
        return JSONObject(result)
    }

    fun generateDiagnosticReport(context: Context): JSONObject {
        prepare(context)
        val result = module(context).callAttr(
            "generate_diagnostic_report",
            workDir(context).absolutePath,
            configFile(context).absolutePath,
            cnAndroidArchives(context).absolutePath,
            dbRoot(context).absolutePath
        ).toString()
        return JSONObject(result)
    }

    fun safeStatus(context: Context, host: String, port: Int): JSONObject {
        if (!Python.isStarted()) {
            return JSONObject()
                .put("phase", "idle")
                .put("running", false)
                .put("tcp_health", socketHealth(host, port, 250))
                .put("host", host)
                .put("port", port)
                .put("thread_alive", false)
                .put("last_error", CrashReporter.read(context))
        }
        return try {
            status(context)
        } catch (t: Throwable) {
            CrashReporter.append(context, "status failed", t)
            JSONObject()
                .put("phase", "status_error")
                .put("running", false)
                .put("tcp_health", socketHealth(host, port, 250))
                .put("host", host)
                .put("port", port)
                .put("thread_alive", false)
                .put("last_error", t.stackTraceToString() + "\n" + CrashReporter.read(context))
        }
    }

    private fun socketHealth(host: String, port: Int, timeoutMs: Int): Boolean {
        return try {
            java.net.Socket().use { socket ->
                socket.connect(java.net.InetSocketAddress(host, port), timeoutMs)
                true
            }
        } catch (_: Throwable) {
            false
        }
    }
}
