<?php
/**
 * 第七境子主题 v1.5
 *  1) 全站加载统一设计样式（水墨风）
 *  2) 站点图标（favicon / apple-touch-icon）
 *  3) 标题、描述与社交分享卡片（Open Graph / Twitter Card）
 *  4) 空段落清理（修「三释」等 flex 区块被空白 <p> 推偏的居中问题）
 *
 * 说明：本文件是站点级设置的唯一真源。若日后安装 Yoast / RankMath 等 SEO 插件，
 *       请把下面「三、标题与分享卡片」整段注释掉，避免 meta 重复输出。
 */

/* ============================================================
   一、样式加载
   ============================================================ */
add_action( 'wp_enqueue_scripts', function () {
	/* 字体加载三改史（别再改回去）：
	   ① 原始：写死在 qijing.css 第 5 行 @import —— 串行阻塞，实测多花 2.5–4.7 秒。
	   ② 改独立 <link> 入队 —— 与 qijing.css 并行下载，字体与观感不变。
	   ③ 2026-10-20 改**异步加载**（REQ-2026-10-20-01，方案 C 止血）：
	      原因 —— fonts.loli.net 是第三方，且它自己也跑在 Cloudflare 上。实测
	      该 CSS 体积 325 KB（333,857 字节）、三次 TTFB 1.73s / 2.97s / 5.33s，
	      字体分片所在的第三个域名 gstatic.loli.net 单次最高 9.76s。
	      它原本是 media='all' 的**渲染阻塞样式**，浏览器必须等它下完才画第一屏；
	      安卓自带浏览器没有云加速、严格执行阻塞，超时就直接判「网页无法打开」。
	      改成 media='print' + onload 还原为 all 之后：不再阻塞首屏，
	      页面先用系统字体画出，字体到位后自动换上（CSS 内已 font-display:swap）。
	      ⚠️ 这只是止血；彻底方案是字体自托管＋子集化（同一份申请单的方案 A）。 */
	wp_enqueue_style(
		'sr-webfonts',
		'https://fonts.loli.net/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600&display=swap',
		array(),
		null
	);
	wp_enqueue_style(
		'qijing',
		get_stylesheet_directory_uri() . '/assets/qijing.css',
		array(),
		'1.7.0'
	);
}, 20 );

/* ============================================================
   一·乙 把 webfont 的 <link> 改成非阻塞（2026-10-20 / REQ-2026-10-20-01）
   WordPress 的 wp_enqueue_style 固定输出 media='all'，浏览器会阻塞渲染等它。
   改成 media='print'（不参与首屏渲染）＋ onload 还原，另加 noscript 兜底：
     · 开 JS 的浏览器：首屏零阻塞，字体后到再换上
     · 关 JS 的浏览器：noscript 那份照常加载，观感不丢
   任何一步没匹配上都原样返回，绝不输出坏标签。
   ============================================================ */
add_filter( 'style_loader_tag', function ( $html, $handle ) {
	if ( 'sr-webfonts' !== $handle ) {
		return $html;
	}
	$async = preg_replace(
		'/media=([\'"])all\1/i',
		"media=\"print\" onload=\"this.media='all'\"",
		$html
	);
	if ( null === $async ) {
		return $html;
	}
	if ( preg_match( '/href=([\'"])(.+?)\1/i', $html, $m ) ) {
		$async .= '<noscript><link rel="stylesheet" href="' . $m[2] . '"></noscript>';
	}
	return $async;
}, 10, 2 );

/* ============================================================
   一·补 空段落清理
   问题：WP 块编辑器常残留空白 <p>（<p>\n</p>）。它在 flex 容器里是
   合法子项，会白吃一个 gap（三释处 100px），把整组内容向左推 50px。
   CSS :empty 匹配不到带换行文本节点的段落，故在服务端输出前剔除：
   无跳动、不依赖 JS、对所有页面生效。
   ============================================================ */
add_filter( 'the_content', function ( $content ) {
	if ( false === strpos( $content, '<p' ) ) {
		return $content;
	}
	// 只删「完全空白」的段落：纯空白字符或 &nbsp;，且不含 img/br/hr
	return preg_replace( '#<p[^>]*>\s*(?:&nbsp;|\s)*</p>\s*#i', '', $content );
}, 20 );

// 块编辑器画布内同步显示水墨版式，编辑所见接近前台
add_action( 'after_setup_theme', function () {
	add_editor_style( 'assets/qijing.css' );
}, 20 );

/* ============================================================
   二、站点图标
   主用子主题自带的「印章 · 七」图标（assets/icon-qi-512.png，512×512）。
   改图标只需替换该文件并重传主题；若文件缺失，回退到媒体库版本。
   ============================================================ */
function sr_site_icon_url() {
	$rel = '/assets/icon-qi-512.png';
	if ( file_exists( get_stylesheet_directory() . $rel ) ) {
		return get_stylesheet_directory_uri() . $rel . '?v=1.6.0';
	}
	$url = function_exists( 'wp_get_attachment_image_url' ) ? wp_get_attachment_image_url( 81, 'full' ) : '';
	if ( ! $url ) {
		$url = 'https://theseventhrealm.com/wp-content/uploads/2026/09/sr-icon-512.png';
	}
	return $url;
}

add_action( 'wp_head', function () {
	$icon = esc_url( sr_site_icon_url() );
	echo '<link rel="icon" type="image/png" sizes="512x512" href="' . $icon . '">' . "\n";
	echo '<link rel="apple-touch-icon" href="' . $icon . '">' . "\n";
	echo '<meta name="theme-color" content="#ffffff">' . "\n";
}, 1 );

/* ============================================================
   四、安全加固（2026-10-04 · REQ-2026-10-04-01）
   背景：外网实测发现三条缺口 ——
     ① /?author=1 → 301 到 /author/admin/，用户名被枚举
     ② /wp-json/wp/v2/users 未登录即可读，吐出了 admin 与 MollyBot_No.2
     ③ 登录入口无失败限制（连试 3 次错误密码全部正常返回 200）
   数据侧证据：机器人访问 /wp-login.php 达 1436 次（比最大真实页面还多 3 倍）
   ============================================================ */

/**
 * 4.0 取真实访客 IP
 * ⚠️ 站点在 Cloudflare 后面：REMOTE_ADDR 永远是 CF 的机房 IP，
 *    用它做限流会把所有访客当成同一个人。必须优先读 CF 头。
 */
if ( ! function_exists( 'sr_client_ip' ) ) :
function sr_client_ip() {
	foreach ( array( 'HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR' ) as $k ) {
		if ( empty( $_SERVER[ $k ] ) ) {
			continue;
		}
		$ip = trim( explode( ',', $_SERVER[ $k ] )[0] );
		if ( filter_var( $ip, FILTER_VALIDATE_IP ) ) {
			return $ip;
		}
	}
	return '0.0.0.0';
}
endif;

/**
 * 4.1 关闭 ?author= 用户名枚举
 * 未登录访客访问 /?author=N 或 /author/xxx/ 一律 301 回首页。
 * ⚠️ 不要加 ! is_author() 条件 —— /?author=1 本身就会被 WordPress 解析成
 *    author 归档，is_author() 本来就是 TRUE，加了之后条件永远不成立。
 *    2026-10-04 实测踩过：加了它，?author=1 照样 301 到 /author/admin/。
 */
add_action( 'template_redirect', function () {
	if ( is_admin() || is_user_logged_in() ) {
		return;
	}
	if ( isset( $_GET['author'] ) || is_author() ) {
		wp_safe_redirect( home_url( '/' ), 301 );
		exit;
	}
}, 1 );

/**
 * 4.2 未登录访客不可读用户列表
 * 只对「没有 edit_posts 能力」的请求摘掉这两个端点；
 * 编辑器和后台作者下拉框照常可用（否则会白屏）。
 */
add_filter( 'rest_endpoints', function ( $endpoints ) {
	if ( is_user_logged_in() && current_user_can( 'edit_posts' ) ) {
		return $endpoints;
	}
	unset( $endpoints['/wp/v2/users'] );
	unset( $endpoints['/wp/v2/users/(?P<id>[\d]+)'] );
	return $endpoints;
} );

/**
 * 4.3 登录失败限流（轻量版，不依赖插件）
 * 同一 IP 15 分钟内失败 ≥5 次即锁定，成功登录后清零。
 * 只拦前台登录；后台已登录用户的正常操作不受影响。
 */
/* ⚠️ 用 define + 存在性判断，不用顶层 const ——
   顶层 const 若本文件被重复 include 会触发致命错误，整站白屏。
   WP 正常只加载一次，但部署方式（插件/自动优化器）可能重复包含。 */
if ( ! defined( 'SR_LOGIN_MAX_FAIL' ) ) {
	define( 'SR_LOGIN_MAX_FAIL', 5 );
}
if ( ! defined( 'SR_LOGIN_WINDOW' ) ) {
	define( 'SR_LOGIN_WINDOW', 900 ); // 15 分钟
}

add_action( 'wp_login_failed', function () {
	if ( is_admin() && is_user_logged_in() ) {
		return;
	}
	$key = 'sr_lf_' . md5( sr_client_ip() );
	set_transient( $key, (int) get_transient( $key ) + 1, SR_LOGIN_WINDOW );
} );

add_filter( 'authenticate', function ( $user, $username, $password ) {
	if ( '' === $username && '' === $password ) {
		return $user; // 空提交不计数
	}
	$key = 'sr_lf_' . md5( sr_client_ip() );
	if ( (int) get_transient( $key ) >= SR_LOGIN_MAX_FAIL ) {
		return new WP_Error(
			'sr_too_many_logins',
			'<strong>尝试次数过多</strong>：请 15 分钟后再试。'
		);
	}
	return $user;
}, 30, 3 );

add_action( 'wp_login', function ( $login, $user ) {
	delete_transient( 'sr_lf_' . md5( sr_client_ip() ) );
}, 10, 2 );

/**
 * 4.4 移除响应头里的 PHP 版本信息
 * 实测 /wp-login.php 返回 x-powered-by: PHP/8.3.33 —— 白送攻击者一个版本号。
 */
add_action( 'init', function () {
	if ( ! is_admin() ) {
		header_remove( 'X-Powered-By' );
	}
} );

/* ============================================================
   三、标题与分享卡片
   ============================================================ */

// 3.1 标题：首页用品牌句，内页用「页面名 · 第七境」
add_filter( 'document_title', function ( $title ) {
	$brand = '第七境';
	if ( is_front_page() || is_home() ) {
		return $brand . ' · 五千年文明的水墨叙事';
	}
	$obj = get_queried_object();
	if ( $obj && ! empty( $obj->post_title ) ) {
		return $obj->post_title . ' · ' . $brand;
	}
	return $title;
}, 20 );

// 3.2 取一段干净纯文本作描述（去掉 script/style 与标签，避免把 JS 写进摘要）
function sr_plain_excerpt( $len = 110 ) {
	if ( ! is_singular() ) {
		return '';
	}
	$post = get_post();
	if ( ! $post ) {
		return '';
	}
	$raw = $post->post_excerpt ? $post->post_excerpt : $post->post_content;
	$raw = preg_replace( '#<(script|style)[^>]*>.*?</\1>#si', '', $raw );
	$txt = trim( preg_replace( '/\s+/u', ' ', wp_strip_all_tags( $raw ) ) );
	if ( function_exists( 'mb_substr' ) && mb_strlen( $txt, 'UTF-8' ) > $len ) {
		$txt = mb_substr( $txt, 0, $len, 'UTF-8' ) . '…';
	}
	return $txt;
}

add_action( 'wp_head', function () {
	$brand   = '第七境';
	$is_home = is_front_page() || is_home();
	$obj     = get_queried_object();
	$name    = ( ! $is_home && $obj && ! empty( $obj->post_title ) ) ? $obj->post_title : $brand;
	$title   = $is_home ? $brand . ' · 五千年文明的水墨叙事' : $name . ' · ' . $brand;
	$desc    = $is_home
		? '以水墨与五千年文明为底色的原创 IP：道境、上下五千年时间线，以及原创的文字与图像。'
		: sr_plain_excerpt( 110 );
	if ( ! $desc ) {
		$desc = '以水墨与五千年文明为底色的原创 IP：道境、上下五千年时间线，以及原创的文字与图像。';
	}
	$url  = ( is_ssl() ? 'https://' : 'http://' ) . ( $_SERVER['HTTP_HOST'] ?? 'theseventhrealm.com' ) . ( $_SERVER['REQUEST_URI'] ?? '/' );
	$img  = sr_site_icon_url();
	$type = $is_home ? 'website' : 'article';

	echo '<meta name="description" content="' . esc_attr( $desc ) . '">' . "\n";
	echo '<meta property="og:type" content="' . esc_attr( $type ) . '">' . "\n";
	echo '<meta property="og:site_name" content="' . esc_attr( $brand ) . '">' . "\n";
	echo '<meta property="og:title" content="' . esc_attr( $title ) . '">' . "\n";
	echo '<meta property="og:description" content="' . esc_attr( $desc ) . '">' . "\n";
	echo '<meta property="og:url" content="' . esc_url( $url ) . '">' . "\n";
	echo '<meta property="og:image" content="' . esc_url( $img ) . '">' . "\n";
	echo '<meta name="twitter:card" content="summary">' . "\n";
	echo '<meta name="twitter:title" content="' . esc_attr( $title ) . '">' . "\n";
	echo '<meta name="twitter:description" content="' . esc_attr( $desc ) . '">' . "\n";
	echo '<meta name="twitter:image" content="' . esc_url( $img ) . '">' . "\n";
}, 2 );
