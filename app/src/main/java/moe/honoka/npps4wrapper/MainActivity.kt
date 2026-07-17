package moe.honoka.npps4wrapper

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.DocumentsContract
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.Window
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import org.json.JSONObject
import java.io.File
import java.net.URLDecoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val blue = Color.rgb(23, 105, 255)
    private val surface = Color.rgb(251, 248, 255)
    private val onSurface = Color.rgb(27, 27, 31)
    private val muted = Color.rgb(92, 95, 103)

    private lateinit var fixedHeader: TextView
    private lateinit var headerToggle: Button
    private lateinit var statusView: TextView
    private lateinit var detailView: TextView
    private lateinit var hostEdit: EditText
    private lateinit var portEdit: EditText
    private lateinit var publicPathEdit: EditText
    private lateinit var pathsView: TextView
    private val logLines = ArrayDeque<String>()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var statusPoller: Runnable? = null
    @Volatile private var statusUpdating = false
    private var lastLoggedStatusError = ""

    private val backupCreateLauncher = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri: Uri? ->
        if (uri != null) runAsync("导出服务器数据备份") {
            FileOps.exportWorkspaceToUri(this, uri)
            "已导出服务器数据备份。备份不包含公共 CDN ZIP 或 master DB。"
        }
    }

    private val backupOpenLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) runAsync("导入服务器数据备份") {
            FileOps.importWorkspaceFromUri(this, uri)
            "已导入服务器数据备份；重启服务后生效。"
        }
    }

    private val publicRootLauncher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? ->
        if (uri != null) {
            val path = publicTreeUriToPath(uri)
            if (path != null) {
                PythonBridge.setPublicBase(this, File(path))
                publicPathEdit.setText(path)
                FileOps.rewriteDefaultConfig(this)
                pathsView.text = pathSummary()
                appendLog("已设置 CDN ZIP 目录：$path")
            } else {
                appendLog("无法把此系统目录 URI 转成普通文件路径：$uri\n请选择包含 .zip 数据包的目录，或直接在路径输入框手动填写。")
            }
        }
    }

    private val storagePermissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val granted = result.values.any { it }
        appendLog(if (granted) "外部存储读写权限已授予。Android 11+ 直读公共目录仍建议授予所有文件访问。" else "外部存储权限未授予；公共路径直读可能失败。")
        if (::pathsView.isInitialized) pathsView.text = pathSummary()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        try { requestWindowFeature(Window.FEATURE_NO_TITLE) } catch (_: Throwable) {}
        super.onCreate(savedInstanceState)
        try {
            actionBar?.hide()
            WindowCompat.setDecorFitsSystemWindows(window, false)
            window.statusBarColor = surface
            window.navigationBarColor = surface
            if (Build.VERSION.SDK_INT >= 23) {
                window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            }
            buildUi()
            appendLog("应用已启动。")
            try { FileOps.ensureTemplate(this) } catch (t: Throwable) { CrashReporter.append(this, "native template init failed", t); appendLog("目录模板创建失败：${t.message}") }
            updateStatus(forceLog = false)
        } catch (t: Throwable) {
            try { CrashReporter.append(this, "MainActivity onCreate failed", t) } catch (_: Throwable) {}
            showFallbackCrashUi(t)
        }
    }

    override fun onResume() {
        super.onResume()
        if (::fixedHeader.isInitialized && ::headerToggle.isInitialized) updateHeaderVisibility()
        if (::pathsView.isInitialized) pathsView.text = pathSummary()
        startStatusPolling(immediate = true)
    }

    override fun onPause() {
        super.onPause()
        stopStatusPolling()
    }

    private fun buildUi() {
        val outer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(surface)
        }
        ViewCompat.setOnApplyWindowInsetsListener(outer) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(0, bars.top, 0, bars.bottom)
            insets
        }
        setContentView(outer)

        fixedHeader = TextView(this).apply {
            text = "LoveArrowShoot!"
            gravity = Gravity.CENTER
            textSize = 30f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(blue)
            setBackgroundColor(surface)
            includeFontPadding = false
        }
        outer.addView(fixedHeader, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(60)))

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(24))
        }
        val scroll = ScrollView(this).apply { clipToPadding = false; setBackgroundColor(surface); addView(root) }
        outer.addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        val titleRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        titleRow.addView(TextView(this).apply {
            text = "NPPS4 Wrapper"
            textSize = 28f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(onSurface)
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        headerToggle = smallToggleButton().apply { setOnClickListener { HeaderState.toggle(this@MainActivity); updateHeaderVisibility() } }
        titleRow.addView(headerToggle, LinearLayout.LayoutParams(dp(48), dp(40)))
        root.addView(titleRow)
        root.addView(TextView(this).apply {
            text = "本机私服 · 国服 CDN 直读路径 · 服务器数据备份"
            textSize = 14f
            setTextColor(muted)
            setPadding(0, dp(2), 0, dp(12))
        })

        val cardsContainer = GridLayout(this).apply {
            columnCount = if (resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE) 2 else 1
            useDefaultMargins = true
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        root.addView(cardsContainer, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))

        cardsContainer.addView(card {
            addView(sectionTitle("服务器状态"))
            statusView = bodyText("状态：未检查")
            statusView.textSize = 15f
            statusView.setTextColor(onSurface)
            addView(statusView)
            addView(button("刷新状态 / 健康检查") { updateStatus(forceLog = true) })
            addView(button("查看完整崩溃/服务错误日志") { openCrashLog() })
            addView(button("生成并查看诊断报告") { generateAndOpenDiagnosticReport() })
            addView(button("清空错误日志") { CrashReporter.file(this@MainActivity).writeText("", Charsets.UTF_8); updateStatus(forceLog = true) })
            detailView = bodyText("最近操作会显示在这里，不会把整段 traceback 堆到主界面。")
            detailView.typeface = Typeface.MONOSPACE
            detailView.setTextIsSelectable(true)
            addView(detailView)
        })

        cardsContainer.addView(card {
            addView(sectionTitle("监听地址"))
            val row = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
            hostEdit = input("Host", "127.0.0.1", InputType.TYPE_CLASS_TEXT).also {
                row.addView(it.parent as View, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 2f).apply { marginEnd = dp(8) })
            }
            portEdit = input("Port", "51376", InputType.TYPE_CLASS_NUMBER).also {
                row.addView(it.parent as View, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            }
            addView(row)
            addView(button("启动服务器") {
                requestNotificationPermission()
                val host = hostEdit.text?.toString().orEmpty().ifBlank { "127.0.0.1" }
                val port = portEdit.text?.toString()?.toIntOrNull() ?: 51376
                appendLog("请求启动服务器：$host:$port")
                FileOps.ensureTemplate(this@MainActivity)
                FileOps.rewriteDefaultConfig(this@MainActivity)
                Npps4Service.start(this@MainActivity, host, port)
                startStatusPolling(immediate = true)
            })
            addView(button("重启服务器") {
                requestNotificationPermission()
                val host = hostEdit.text?.toString().orEmpty().ifBlank { "127.0.0.1" }
                val port = portEdit.text?.toString()?.toIntOrNull() ?: 51376
                appendLog("请求重启服务器：$host:$port")
                FileOps.ensureTemplate(this@MainActivity)
                FileOps.rewriteDefaultConfig(this@MainActivity)
                Npps4Service.restart(this@MainActivity, host, port)
                startStatusPolling(immediate = true)
            })
            addView(button("停止服务器") {
                appendLog("请求停止服务器")
                Npps4Service.stop(this@MainActivity)
                startStatusPolling(immediate = true)
            })
        })

        cardsContainer.addView(card {
            addView(sectionTitle("下载后端 / 区服快捷配置"))
            addView(bodyText("当前下载模式：${downloadProfileLabel()}\n国服：客户端和资源 ZIP 都走本地 cn_archive；国际服：客户端 API 走本地 127.0.0.1:8080，数据包 URL 由 NPPS4-DLAPI 在线返回。切换后需要重启服务端。"))
            addView(button("一键切换：国服本地 CDN 数据包（cn_archive）") {
                runAsync("切换国服本地 CDN 模式") {
                    FileOps.configureCnArchive(this@MainActivity) + "\n" + FileOps.checkPublicPaths(this@MainActivity)
                }
            })
            addView(button("一键切换：国际服在线 DLAPI/CDN 数据包") {
                runAsync("切换国际服在线 DLAPI/CDN 模式") {
                    FileOps.configureGlOnlineDlapi(this@MainActivity) + "\nDLAPI: ${FileOps.ONLINE_DLAPI_SERVER}"
                }
            })
            addView(button("编辑 config.toml 查看当前配置") { ConfigEditorActivity.open(this@MainActivity, PythonBridge.configFile(this@MainActivity).absolutePath, "config.toml") })
        })

        cardsContainer.addView(card {
            addView(sectionTitle("路径映射 / 本机 CDN"))
            publicPathEdit = input("CDN ZIP 目录（直接选择包含 .zip 的文件夹，名称不限）", PythonBridge.publicBase(this@MainActivity).absolutePath, InputType.TYPE_CLASS_TEXT)
            addView(publicPathEdit.parent as View)
            pathsView = bodyText(pathSummary())
            pathsView.setTextIsSelectable(true)
            addView(pathsView)
            addView(bodyText("这里只配置只读 CDN 目录；普通 ZIP 和 99_0_115.zip 都不会被 Wrapper 编辑。master DB 使用内置 honoka main.db 生成到工作区。国际服在线 DLAPI 模式不依赖这个目录。"))
            addView(button("选择 CDN ZIP 目录（不复制文件）") { publicRootLauncher.launch(null) })
            addView(button("保存路径并检查") {
                val path = publicPathEdit.text?.toString().orEmpty().ifBlank { "/storage/emulated/0/NPPS4" }
                PythonBridge.setPublicBase(this@MainActivity, File(path))
                runAsync("保存路径并检查") { FileOps.ensureTemplate(this@MainActivity); FileOps.rewriteDefaultConfig(this@MainActivity); "已保存 CDN ZIP 目录：$path\n" + FileOps.checkPublicPaths(this@MainActivity) }
            })
            addView(button("生成/刷新内置 honoka CN master DB") { runAsync("生成 master DB") { PythonBridge.extractMasterDb(this@MainActivity).toString(2) } })
            addView(button("打开所有文件访问权限设置") { openAllFilesAccessSettings() })
        })

        cardsContainer.addView(card {
            addView(sectionTitle("备份 / 迁移"))
            addView(button("一键导出服务器数据备份 ZIP") { backupCreateLauncher.launch(FileOps.defaultBackupName()) })
            addView(button("从 ZIP 导入服务器数据备份") { backupOpenLauncher.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) })
            addView(bodyText("备份只包含服务器账户/进度数据库、配置、server_data.json 和 external 脚本；不包含公共目录里的 CDN 数据包。内置 honoka master DB 可重新生成。"))
        })

        cardsContainer.addView(card {
            addView(sectionTitle("关键数据编辑"))
            addView(button("编辑 config.toml") { ConfigEditorActivity.open(this@MainActivity, PythonBridge.configFile(this@MainActivity).absolutePath, "config.toml") })
            addView(button("编辑 server_data.json") { ConfigEditorActivity.open(this@MainActivity, PythonBridge.serverDataFile(this@MainActivity).absolutePath, "server_data.json") })
            addView(button("编辑 external/login_bonus.py") { ConfigEditorActivity.open(this@MainActivity, File(PythonBridge.workDir(this@MainActivity), "external/login_bonus.py").absolutePath, "login_bonus.py") })
            addView(button("热重载可编辑数据（不停服）") {
                runAsync("热重载可编辑数据") { PythonBridge.reloadEditableData(this@MainActivity).toString(2) }
                startStatusPolling(immediate = true)
            })
            addView(bodyText("server_data.json 和 external/*.py 可不停服重载；监听端口、数据库 URL、下载后端这类 config.toml 结构性改动仍需重启服务。"))
        })
        for (i in 0 until cardsContainer.childCount) {
            val child = cardsContainer.getChildAt(i)
            child.layoutParams = GridLayout.LayoutParams().apply {
                width = 0
                height = GridLayout.LayoutParams.WRAP_CONTENT
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
                setMargins(dp(4), dp(4), dp(4), dp(4))
            }
        }
        updateHeaderVisibility()
    }

    private fun card(build: LinearLayout.() -> Unit): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = roundedBackground(Color.WHITE, dp(24), Color.rgb(225, 229, 236), 1)
        elevation = dp(1).toFloat()
        setPadding(dp(16), dp(14), dp(16), dp(14))
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(12) }
        build()
    }

    private fun sectionTitle(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 18f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(onSurface)
        setPadding(0, 0, 0, dp(8))
    }

    private fun bodyText(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(muted)
        setLineSpacing(0f, 1.08f)
        setPadding(0, dp(4), 0, dp(8))
    }

    private fun button(text: String, action: (View) -> Unit): Button = Button(this).apply {
        this.text = text
        isAllCaps = false
        setTextColor(Color.WHITE)
        textSize = 15f
        typeface = Typeface.DEFAULT_BOLD
        background = roundedBackground(blue, dp(18))
        setPadding(dp(12), dp(10), dp(12), dp(10))
        setOnClickListener(action)
        minHeight = dp(48)
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(6) }
    }

    private fun smallToggleButton(): Button = Button(this).apply {
        isAllCaps = false
        textSize = 18f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.WHITE)
        background = roundedBackground(blue, dp(16))
        minWidth = dp(48)
        minimumWidth = dp(48)
        minHeight = dp(40)
        setPadding(0, 0, 0, 0)
    }

    private fun input(label: String, value: String, inputType: Int): EditText {
        val wrapper = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        wrapper.addView(TextView(this).apply { text = label; textSize = 12f; setTextColor(muted); setPadding(dp(4), 0, dp(4), dp(3)) })
        val edit = EditText(this).apply {
            setText(value)
            this.inputType = inputType
            setSingleLine(true)
            textSize = 15f
            setTextColor(onSurface)
            setPadding(dp(12), 0, dp(12), 0)
            minHeight = dp(52)
            background = roundedBackground(Color.rgb(245, 247, 252), dp(14), Color.rgb(196, 201, 212), 1)
        }
        wrapper.addView(edit)
        return edit
    }

    private fun roundedBackground(fill: Int, radius: Int, strokeColor: Int? = null, strokeWidthDp: Int = 0): GradientDrawable = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        setColor(fill)
        cornerRadius = radius.toFloat()
        if (strokeColor != null && strokeWidthDp > 0) setStroke(dp(strokeWidthDp), strokeColor)
    }


    private fun downloadProfileLabel(): String = when (FileOps.getDownloadProfile(this)) {
        FileOps.PROFILE_GL_ONLINE_DLAPI -> "国际服在线 DLAPI/CDN（n4dlapi → ${FileOps.ONLINE_DLAPI_SERVER}）"
        else -> "国服本地 CDN（cn_archive）"
    }

    private fun pathSummary(): String = """
工作区: ${PythonBridge.workDir(this).absolutePath}
CDN ZIP 目录: ${PythonBridge.cnAndroidArchives(this).absolutePath}
99_0_115: ${File(PythonBridge.cnAndroidArchives(this), "99_0_115.zip").absolutePath}
内置 master DB 输出目录: ${PythonBridge.dbRoot(this).absolutePath}
服务地址: http://${hostEdit.text}:${portEdit.text}/
下载模式: ${downloadProfileLabel()}
外部存储模式: ${storageModeSummary()}
""".trimIndent()

    private fun updateStatus(forceLog: Boolean = false) {
        if (!::statusView.isInitialized || statusUpdating) return
        statusUpdating = true
        val host = hostEdit.text?.toString().orEmpty().ifBlank { "127.0.0.1" }
        val port = portEdit.text?.toString()?.toIntOrNull() ?: 51376
        Thread {
            val pair = try {
                val s: JSONObject = PythonBridge.safeStatus(this, host, port)
                val phase = s.optString("phase", "idle")
                val running = s.optBoolean("running")
                val tcp = s.optBoolean("tcp_health")
                val thread = s.optBoolean("thread_alive")
                val lastError = s.optString("last_error")
                if (lastError.isNotBlank() && phase == "error") {
                    val compactError = lastError.take(12000)
                    if (compactError != lastLoggedStatusError) {
                        lastLoggedStatusError = compactError
                        CrashReporter.append(this, "NPPS4 Python state error", RuntimeException(compactError))
                    }
                } else if (lastError.isBlank()) {
                    lastLoggedStatusError = ""
                }
                val label = when {
                    running && tcp -> "运行中"
                    phase == "error" -> "启动失败"
                    phase == "preparing" || phase == "migrating" -> "启动中：$phase"
                    tcp -> "端口可连接，但 Python 状态未知"
                    else -> "未运行"
                }
                val summary = buildString {
                    append("服务器：$label\n")
                    append("监听：$host:$port\n")
                    append("TCP：${if (tcp) "可连接" else "不可连接"}，线程：${if (thread) "存在" else "无"}\n")
                    if (lastError.isNotBlank()) append("最近错误：${summarizeError(lastError)}")
                }
                summary to if (lastError.isBlank()) "状态已刷新。" else "完整错误已写入 npps4-wrapper-crash.log。"
            } catch (t: Throwable) {
                CrashReporter.append(this, "safeStatus failed", t)
                "状态读取失败：${t.javaClass.simpleName}" to summarizeError(t.stackTraceToString())
            }
            runOnUiThread {
                statusUpdating = false
                statusView.text = pair.first
                if (forceLog) {
                    appendLog(pair.second)
                    if (::pathsView.isInitialized) pathsView.text = pathSummary()
                }
            }
        }.start()
    }

    private fun startStatusPolling(immediate: Boolean = false) {
        stopStatusPolling()
        val poller = object : Runnable {
            override fun run() {
                if (::statusView.isInitialized) updateStatus(forceLog = false)
                mainHandler.postDelayed(this, 2000L)
            }
        }
        statusPoller = poller
        if (immediate) {
            if (::statusView.isInitialized) updateStatus(forceLog = false)
            mainHandler.postDelayed(poller, 2000L)
        } else {
            mainHandler.postDelayed(poller, 2000L)
        }
    }

    private fun stopStatusPolling() {
        statusPoller?.let { mainHandler.removeCallbacks(it) }
        statusPoller = null
    }

    private fun summarizeError(text: String): String {
        val lines = text.lines().filter { it.isNotBlank() }
        val interesting = lines.firstOrNull { it.contains("Error") || it.contains("Exception") || it.contains("RuntimeError") } ?: lines.firstOrNull().orEmpty()
        val tail = lines.lastOrNull { !it.trim().startsWith("at ") && !it.trim().startsWith("File ") }.orEmpty()
        return listOf(interesting, tail).filter { it.isNotBlank() }.distinct().joinToString(" | ").take(600)
    }

    private fun runAsync(title: String, block: () -> String) {
        appendLog("$title...")
        Thread {
            val msg = try { block() } catch (t: Throwable) { CrashReporter.append(this, title, t); "失败：${summarizeError(t.stackTraceToString())}" }
            runOnUiThread {
                appendLog(msg)
                detailView.text = msg.take(1200)
                pathsView.text = pathSummary()
                updateStatus(forceLog = false)
            }
        }.start()
    }

    private fun appendLog(text: String) {
        val ts = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        logLines.addFirst("[$ts] ${text.take(1000)}")
        while (logLines.size > 4) logLines.removeLast()
        detailView.text = logLines.joinToString("\n\n")
    }

    private fun updateHeaderVisibility() {
        val hidden = HeaderState.isHidden(this)
        fixedHeader.visibility = if (hidden) View.GONE else View.VISIBLE
        // The button indicates the action: when the bar is hidden, show ▼ to pull it down;
        // when the bar is visible, show ▲ to collapse it.
        headerToggle.text = if (hidden) "▼" else "▲"
    }

    private fun storageModeSummary(): String {
        val legacy = try { if (Build.VERSION.SDK_INT >= 29) Environment.isExternalStorageLegacy() else true } catch (_: Throwable) { false }
        val readGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
        val writeGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
        val allFiles = hasAllFilesAccess()
        return when {
            allFiles -> "MANAGE_EXTERNAL_STORAGE 已授予"
            legacy && (readGranted || Build.VERSION.SDK_INT < 23) -> "普通外部存储权限可用"
            legacy -> "Android 10 及以下可用 READ/WRITE；Android 11+ 直读公共目录需要所有文件访问"
            else -> "受 scoped storage 限制；Android 11+ 请授予所有文件访问，或使用应用专属直读目录"
        }
    }

    private fun requestLegacyStoragePermissions() {
        if (Build.VERSION.SDK_INT < 23) {
            appendLog("Android 6 以下无需运行时存储权限。")
            return
        }
        val permissions = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) permissions += Manifest.permission.READ_EXTERNAL_STORAGE
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) permissions += Manifest.permission.WRITE_EXTERNAL_STORAGE
        if (permissions.isEmpty()) {
            appendLog("外部存储读写权限已授予。${storageModeSummary()}")
            return
        }
        storagePermissionLauncher.launch(permissions.toTypedArray())
    }

    private fun hasAllFilesAccess(): Boolean = Build.VERSION.SDK_INT < 30 || Environment.isExternalStorageManager()

    private fun openAllFilesAccessSettings() {
        if (Build.VERSION.SDK_INT >= 30) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply { data = Uri.parse("package:$packageName") })
            } catch (_: Throwable) {
                try { startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)) }
                catch (_: Throwable) { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply { data = Uri.parse("package:$packageName") }) }
            }
            appendLog("已打开所有文件访问设置。v3.1 已使用 targetSdk=35 + MANAGE_EXTERNAL_STORAGE；如果开关仍然灰掉，请确认安装的是 0.3.1 版本，或用 ADB：adb shell appops set $packageName MANAGE_EXTERNAL_STORAGE allow")
        } else appendLog("Android 10 或更低版本通常不需要所有文件访问权限。")
    }

    private fun generateAndOpenDiagnosticReport() {
        appendLog("正在生成诊断报告：检查 CN ZIP 资源、公告/招募关键资产、Museum 桥接与当前解锁策略……")
        Thread {
            try {
                val result = PythonBridge.generateDiagnosticReport(this)
                val path = result.optString("path")
                if (path.isBlank()) error("诊断报告没有返回文件路径：$result")
                runOnUiThread {
                    appendLog("诊断报告已生成：$path")
                    ConfigEditorActivity.open(this, path, "诊断报告日志")
                }
            } catch (t: Throwable) {
                CrashReporter.append(this, "生成诊断报告", t)
                runOnUiThread { appendLog("诊断报告生成失败：${t.javaClass.simpleName}: ${t.message}") }
            }
        }.start()
    }

    private fun openCrashLog() {
        ConfigEditorActivity.open(this, CrashReporter.file(this).absolutePath, "日志")
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 10)
        }
    }

    private fun publicTreeUriToPath(uri: Uri): String? {
        return try {
            if (uri.scheme == "file") return uri.path
            if (Build.VERSION.SDK_INT >= 21 && uri.authority == "com.android.externalstorage.documents") {
                val treeId = DocumentsContract.getTreeDocumentId(uri)
                val decoded = URLDecoder.decode(treeId, "UTF-8")
                val parts = decoded.split(":", limit = 2)
                val volume = parts.getOrNull(0) ?: return null
                val rel = parts.getOrNull(1).orEmpty()
                when (volume.lowercase(Locale.US)) {
                    "primary" -> if (rel.isBlank()) "/storage/emulated/0" else "/storage/emulated/0/$rel"
                    else -> if (rel.isBlank()) "/storage/$volume" else "/storage/$volume/$rel"
                }
            } else null
        } catch (_: Throwable) { null }
    }

    private fun showFallbackCrashUi(t: Throwable) {
        val text = TextView(this).apply {
            this.text = "NPPS4 Wrapper 主界面初始化失败\n\n${t.stackTraceToString()}\n\n错误已写入 npps4-wrapper-crash.log。"
            textSize = 14f
            setTextIsSelectable(true)
            setPadding(dp(16), dp(48), dp(16), dp(16))
        }
        setContentView(ScrollView(this).apply { addView(text) })
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
