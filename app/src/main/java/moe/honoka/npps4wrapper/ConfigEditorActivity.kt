package moe.honoka.npps4wrapper

import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.Editable
import android.text.InputType
import android.text.method.TextKeyListener
import android.text.TextWatcher
import android.util.AttributeSet
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.view.ViewParent
import android.view.ViewConfiguration
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import java.io.File
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * EditText subclass which exposes Android's real scroll metrics to the custom,
 * touch-draggable scrollbars. The framework's built-in scrollbars are only
 * position indicators and cannot be dragged by the user.
 */
private class ScrollMetricEditText @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
    defStyleRes: Int = 0,
) : EditText(context, attrs, defStyleAttr, defStyleRes) {
    private var readOnlyMode = false
    private var touchDownX = 0f
    private var touchDownY = 0f
    private var focusedBeforeTouch = false

    fun verticalRangePx(): Int = computeVerticalScrollRange()
    fun verticalExtentPx(): Int = computeVerticalScrollExtent()
    fun verticalOffsetPx(): Int = computeVerticalScrollOffset()
    fun horizontalRangePx(): Int = computeHorizontalScrollRange()
    fun horizontalExtentPx(): Int = computeHorizontalScrollExtent()
    fun horizontalOffsetPx(): Int = computeHorizontalScrollOffset()

    fun configureEditable(editable: Boolean) {
        readOnlyMode = !editable
        isEnabled = true
        isClickable = true
        isLongClickable = true
        if (editable) {
            // setTextIsSelectable(false) can reset focus/movement flags on some
            // Android builds, so restore the editor state after calling it.
            setTextIsSelectable(false)
            keyListener = TextKeyListener.getInstance()
            isFocusable = true
            isFocusableInTouchMode = true
            isCursorVisible = true
            showSoftInputOnFocus = false
        } else {
            keyListener = null
            setTextIsSelectable(true)
            isFocusable = true
            isFocusableInTouchMode = true
            isCursorVisible = false
            showSoftInputOnFocus = false
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!readOnlyMode && event.actionMasked == MotionEvent.ACTION_DOWN) {
            touchDownX = event.x
            touchDownY = event.y
            focusedBeforeTouch = hasFocus()
            requestFocusFromTouch()
            var ancestor: ViewParent? = parent
            while (ancestor != null) {
                ancestor.requestDisallowInterceptTouchEvent(true)
                ancestor = ancestor.parent
            }
        }

        val handled = super.onTouchEvent(event)

        if (!readOnlyMode && event.actionMasked == MotionEvent.ACTION_UP) {
            val slop = ViewConfiguration.get(context).scaledTouchSlop.toFloat()
            val isTap = abs(event.x - touchDownX) <= slop && abs(event.y - touchDownY) <= slop
            // A drag is for scrolling. The first stationary tap only focuses and
            // positions the cursor; a second deliberate tap opens the keyboard.
            if (isTap && focusedBeforeTouch && hasFocus()) {
                post {
                    (context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager)
                        ?.showSoftInput(this, InputMethodManager.SHOW_IMPLICIT)
                }
            }
        }

        if (event.actionMasked == MotionEvent.ACTION_UP || event.actionMasked == MotionEvent.ACTION_CANCEL) {
            postDelayed({
                var ancestor: ViewParent? = parent
                while (ancestor != null) {
                    ancestor.requestDisallowInterceptTouchEvent(false)
                    ancestor = ancestor.parent
                }
            }, 60L)
        }
        return handled
    }
}

/**
 * A real draggable scrollbar. It draws a permanent track and thumb, supports
 * tapping the track, and sends a normalized 0..1 position while dragging.
 */
private class DragScrollbarView(
    context: Context,
    private val orientation: Int,
) : View(context) {
    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(212, 217, 226)
        style = Paint.Style.FILL
    }
    private val thumbPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(23, 105, 255)
        style = Paint.Style.FILL
    }
    private val insetPx = dp(5).toFloat()
    private val trackThicknessPx = dp(4).toFloat()
    private val thumbThicknessPx = dp(12).toFloat()
    private val minThumbLengthPx = dp(40).toFloat()

    private var positionFraction = 0f
    private var extentFraction = 1f
    private var dragging = false
    private var dragOffsetPx = 0f

    var onPositionChanged: ((Float) -> Unit)? = null

    init {
        isClickable = true
        isFocusable = true
    }

    fun setMetrics(position: Float, extent: Float, enabled: Boolean) {
        positionFraction = position.coerceIn(0f, 1f)
        extentFraction = extent.coerceIn(0.04f, 1f)
        isEnabled = enabled
        alpha = if (enabled) 1f else 0.45f
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val trackStart = insetPx
        val trackLength = usableTrackLength()
        if (trackLength <= 0f) return

        val thumbLength = thumbLength(trackLength)
        val thumbStart = trackStart + (trackLength - thumbLength) * positionFraction
        val radius = thumbThicknessPx / 2f

        if (orientation == VERTICAL) {
            val centerX = width / 2f
            canvas.drawRoundRect(
                centerX - trackThicknessPx / 2f,
                trackStart,
                centerX + trackThicknessPx / 2f,
                trackStart + trackLength,
                trackThicknessPx / 2f,
                trackThicknessPx / 2f,
                trackPaint,
            )
            canvas.drawRoundRect(
                centerX - thumbThicknessPx / 2f,
                thumbStart,
                centerX + thumbThicknessPx / 2f,
                thumbStart + thumbLength,
                radius,
                radius,
                thumbPaint,
            )
        } else {
            val centerY = height / 2f
            canvas.drawRoundRect(
                trackStart,
                centerY - trackThicknessPx / 2f,
                trackStart + trackLength,
                centerY + trackThicknessPx / 2f,
                trackThicknessPx / 2f,
                trackThicknessPx / 2f,
                trackPaint,
            )
            canvas.drawRoundRect(
                thumbStart,
                centerY - thumbThicknessPx / 2f,
                thumbStart + thumbLength,
                centerY + thumbThicknessPx / 2f,
                radius,
                radius,
                thumbPaint,
            )
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!isEnabled) return true

        val coordinate = if (orientation == VERTICAL) event.y else event.x
        val trackLength = usableTrackLength()
        val thumbLength = thumbLength(trackLength)
        val thumbStart = insetPx + (trackLength - thumbLength) * positionFraction

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                parent?.requestDisallowInterceptTouchEvent(true)
                dragging = true
                dragOffsetPx = if (coordinate in thumbStart..(thumbStart + thumbLength)) {
                    coordinate - thumbStart
                } else {
                    thumbLength / 2f
                }
                updateFromTouch(coordinate, trackLength, thumbLength)
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                if (dragging) updateFromTouch(coordinate, trackLength, thumbLength)
                return true
            }

            MotionEvent.ACTION_UP -> {
                if (dragging) updateFromTouch(coordinate, trackLength, thumbLength)
                dragging = false
                parent?.requestDisallowInterceptTouchEvent(false)
                performClick()
                return true
            }

            MotionEvent.ACTION_CANCEL -> {
                dragging = false
                parent?.requestDisallowInterceptTouchEvent(false)
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    private fun updateFromTouch(coordinate: Float, trackLength: Float, thumbLength: Float) {
        val movableLength = (trackLength - thumbLength).coerceAtLeast(0f)
        val newPosition = if (movableLength == 0f) {
            0f
        } else {
            ((coordinate - dragOffsetPx - insetPx) / movableLength).coerceIn(0f, 1f)
        }
        if (newPosition != positionFraction) {
            positionFraction = newPosition
            invalidate()
            onPositionChanged?.invoke(newPosition)
        }
    }

    private fun usableTrackLength(): Float {
        val full = if (orientation == VERTICAL) height.toFloat() else width.toFloat()
        return (full - 2f * insetPx).coerceAtLeast(0f)
    }

    private fun thumbLength(trackLength: Float): Float =
        max(minThumbLengthPx, trackLength * extentFraction).coerceAtMost(trackLength)

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    companion object {
        const val VERTICAL = 1
        const val HORIZONTAL = 2
    }
}

class ConfigEditorActivity : ComponentActivity() {
    private val blue = Color.rgb(23, 105, 255)
    private val surface = Color.rgb(251, 248, 255)
    private val onSurface = Color.rgb(27, 27, 31)
    private val muted = Color.rgb(92, 95, 103)
    private lateinit var fixedHeader: TextView
    private lateinit var headerToggle: Button
    private lateinit var file: File
    private lateinit var editor: ScrollMetricEditText
    private lateinit var verticalScrollbar: DragScrollbarView
    private lateinit var horizontalScrollbar: DragScrollbarView
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        try { requestWindowFeature(Window.FEATURE_NO_TITLE) } catch (_: Throwable) {}
        super.onCreate(savedInstanceState)
        try { actionBar?.hide() } catch (_: Throwable) {}
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = surface
        window.navigationBarColor = surface
        if (Build.VERSION.SDK_INT >= 23) {
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        }
        file = File(intent.getStringExtra(EXTRA_PATH) ?: error("missing path"))
        val title = intent.getStringExtra(EXTRA_TITLE) ?: file.name
        buildUi(title)
    }

    override fun onResume() {
        super.onResume()
        if (::fixedHeader.isInitialized && ::headerToggle.isInitialized) updateHeaderVisibility()
        if (::editor.isInitialized) editor.post { updateScrollbars() }
    }

    private fun buildUi(title: String) {
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
        val scroll = ScrollView(this).apply {
            clipToPadding = false
            isFillViewport = true
            descendantFocusability = ViewGroup.FOCUS_AFTER_DESCENDANTS
            setBackgroundColor(surface)
            addView(root)
        }
        outer.addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        val topRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        topRow.addView(Button(this).apply {
            text = "←"
            contentDescription = "返回"
            minWidth = dp(48)
            minimumWidth = dp(48)
            isAllCaps = false
            textSize = 20f
            setTextColor(Color.WHITE)
            background = roundedBackground(blue, dp(16))
            setOnClickListener { finish() }
        }, LinearLayout.LayoutParams(dp(56), dp(44)).apply { marginEnd = dp(10) })
        val isLogViewer = title.contains("日志") || file.name.endsWith(".log", ignoreCase = true)
        topRow.addView(TextView(this).apply {
            text = if (isLogViewer) "查看 $title" else "编辑 $title"
            textSize = 24f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(onSurface)
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        headerToggle = Button(this).apply {
            isAllCaps = false
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
            background = roundedBackground(blue, dp(16))
            setPadding(0, 0, 0, 0)
            setOnClickListener { HeaderState.toggle(this@ConfigEditorActivity); updateHeaderVisibility() }
        }
        topRow.addView(headerToggle, LinearLayout.LayoutParams(dp(48), dp(44)))
        root.addView(topRow)

        root.addView(TextView(this).apply {
            text = file.absolutePath
            textSize = 12f
            setTextColor(muted)
            setTextIsSelectable(true)
            setPadding(0, dp(4), 0, dp(12))
        })
        root.addView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = roundedBackground(Color.WHITE, dp(24), Color.rgb(225, 229, 236), 1)
            elevation = dp(1).toFloat()
            setPadding(dp(14), dp(12), dp(14), dp(12))

            val sizeRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
            sizeRow.addView(button("字号 -") {
                editor.textSize = (editor.textSize / resources.displayMetrics.scaledDensity - 1f).coerceAtLeast(10f)
                editor.post { updateScrollbars() }
            }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { marginEnd = dp(6) })
            sizeRow.addView(button("字号 +") {
                editor.textSize = (editor.textSize / resources.displayMetrics.scaledDensity + 1f).coerceAtMost(28f)
                editor.post { updateScrollbars() }
            }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(sizeRow)

            val editorFrame = FrameLayout(context).apply {
                background = roundedBackground(Color.rgb(245, 247, 252), dp(14), Color.rgb(196, 201, 212), 1)
            }

            editor = ScrollMetricEditText(context).apply {
                setText(if (file.exists()) file.readText(Charsets.UTF_8) else "")
                setHorizontallyScrolling(true)
                // Built-in Android scrollbars are intentionally disabled here:
                // they are non-interactive indicators and caused a Samsung
                // ScrollBarDrawable NPE in v4.46. The two custom bars below are
                // permanent, touch-draggable controls.
                isVerticalScrollBarEnabled = false
                isHorizontalScrollBarEnabled = false
                overScrollMode = View.OVER_SCROLL_NEVER
                minLines = 18
                gravity = Gravity.TOP or Gravity.START
                typeface = Typeface.MONOSPACE
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
                setSingleLine(false)
                configureEditable(!isLogViewer)
                setBackgroundColor(Color.TRANSPARENT)
                setPadding(dp(12), dp(10), dp(12), dp(10))
                setOnScrollChangeListener { _, _, _, _, _ -> updateScrollbars() }
                addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ -> post { updateScrollbars() } }
                val editorView = this
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                    override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
                    override fun afterTextChanged(s: Editable?) { editorView.post { updateScrollbars() } }
                })
            }
            editorFrame.addView(editor, FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ).apply {
                marginEnd = dp(30)
                bottomMargin = dp(30)
            })

            verticalScrollbar = DragScrollbarView(context, DragScrollbarView.VERTICAL).apply {
                contentDescription = "垂直滚动条，可上下拖动"
                onPositionChanged = { fraction ->
                    val maxScroll = (editor.verticalRangePx() - editor.verticalExtentPx()).coerceAtLeast(0)
                    editor.scrollTo(editor.scrollX, (maxScroll * fraction).roundToInt())
                }
            }
            editorFrame.addView(verticalScrollbar, FrameLayout.LayoutParams(
                dp(30),
                FrameLayout.LayoutParams.MATCH_PARENT,
                Gravity.END,
            ).apply { bottomMargin = dp(30) })

            horizontalScrollbar = DragScrollbarView(context, DragScrollbarView.HORIZONTAL).apply {
                contentDescription = "水平滚动条，可左右拖动"
                onPositionChanged = { fraction ->
                    val maxScroll = (editor.horizontalRangePx() - editor.horizontalExtentPx()).coerceAtLeast(0)
                    editor.scrollTo((maxScroll * fraction).roundToInt(), editor.scrollY)
                }
            }
            editorFrame.addView(horizontalScrollbar, FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                dp(30),
                Gravity.BOTTOM,
            ).apply { marginEnd = dp(30) })

            editorFrame.addView(View(context).apply {
                setBackgroundColor(Color.rgb(245, 247, 252))
            }, FrameLayout.LayoutParams(dp(30), dp(30), Gravity.END or Gravity.BOTTOM))

            addView(editorFrame, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

            status = TextView(context).apply {
                text = if (isLogViewer) {
                    "日志为只读；可拖动右侧和底部蓝色滑块滚动，也可用上方按钮调节字号。"
                } else {
                    "可拖动右侧和底部蓝色滑块滚动。修改后保存，重启服务生效。"
                }
                textSize = 13f
                setTextColor(muted)
                setPadding(0, dp(8), 0, dp(4))
            }
            addView(status)
            if (!isLogViewer) {
                addView(button("保存") {
                    file.parentFile?.mkdirs()
                    file.writeText(editor.text.toString(), Charsets.UTF_8)
                    status.text = "已保存：${file.name}。可点击下方热重载；结构性 config 改动仍需重启服务。"
                })
                addView(button("保存并热重载") {
                    file.parentFile?.mkdirs()
                    file.writeText(editor.text.toString(), Charsets.UTF_8)
                    Thread {
                        val msg = try {
                            PythonBridge.reloadEditableData(this@ConfigEditorActivity).toString(2)
                        } catch (t: Throwable) {
                            CrashReporter.append(this@ConfigEditorActivity, "保存并热重载", t)
                            "热重载失败：${t.javaClass.simpleName}: ${t.message}"
                        }
                        runOnUiThread { status.text = msg.take(1200) }
                    }.start()
                })
            } else {
                addView(button("刷新日志") {
                    editor.setText(if (file.exists()) file.readText(Charsets.UTF_8) else "")
                    editor.post { updateScrollbars() }
                    status.text = "已刷新。"
                })
            }
            addView(button("返回") { finish() })
        }, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(640)))
        updateHeaderVisibility()
        editor.post { updateScrollbars() }
    }

    private fun updateScrollbars() {
        if (!::editor.isInitialized || !::verticalScrollbar.isInitialized || !::horizontalScrollbar.isInitialized) return

        val verticalRange = editor.verticalRangePx().coerceAtLeast(1)
        val verticalExtent = editor.verticalExtentPx().coerceAtLeast(1)
        val verticalMax = (verticalRange - verticalExtent).coerceAtLeast(0)
        val verticalPosition = if (verticalMax == 0) 0f else {
            editor.verticalOffsetPx().toFloat().div(verticalMax).coerceIn(0f, 1f)
        }
        verticalScrollbar.setMetrics(
            verticalPosition,
            verticalExtent.toFloat().div(verticalRange).coerceIn(0.04f, 1f),
            verticalMax > 0,
        )

        val horizontalRange = editor.horizontalRangePx().coerceAtLeast(1)
        val horizontalExtent = editor.horizontalExtentPx().coerceAtLeast(1)
        val horizontalMax = (horizontalRange - horizontalExtent).coerceAtLeast(0)
        val horizontalPosition = if (horizontalMax == 0) 0f else {
            editor.horizontalOffsetPx().toFloat().div(horizontalMax).coerceIn(0f, 1f)
        }
        horizontalScrollbar.setMetrics(
            horizontalPosition,
            horizontalExtent.toFloat().div(horizontalRange).coerceIn(0.04f, 1f),
            horizontalMax > 0,
        )
    }

    private fun updateHeaderVisibility() {
        val hidden = HeaderState.isHidden(this)
        fixedHeader.visibility = if (hidden) View.GONE else View.VISIBLE
        headerToggle.text = if (hidden) "▼" else "▲"
    }

    private fun button(text: String, action: () -> Unit): Button = Button(this).apply {
        this.text = text
        isAllCaps = false
        textSize = 15f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.WHITE)
        background = roundedBackground(blue, dp(18))
        setOnClickListener { action() }
        minHeight = dp(48)
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(6) }
    }

    private fun roundedBackground(fill: Int, radius: Int, strokeColor: Int? = null, strokeWidthDp: Int = 0): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            setColor(fill)
            cornerRadius = radius.toFloat()
            if (strokeColor != null && strokeWidthDp > 0) setStroke(dp(strokeWidthDp), strokeColor)
        }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    companion object {
        private const val EXTRA_PATH = "path"
        private const val EXTRA_TITLE = "title"
        fun open(context: Context, path: String, title: String) {
            context.startActivity(Intent(context, ConfigEditorActivity::class.java).putExtra(EXTRA_PATH, path).putExtra(EXTRA_TITLE, title))
        }
    }
}
