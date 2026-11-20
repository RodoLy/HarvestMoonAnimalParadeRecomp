// What the app shows first. It gets the game ready and starts it:
//
// 1. Unpacks the game's files from the app (assets/game: dsp_coef.bin, wii_bootstrap, ...) to
//    Game/ in the app's folder, once per version of the app.
// 2. Writes portable.txt (settings, saves and logs go to UserData/) and, the first time,
//    UserData/Config.toml with the disc's folder.
// 3. Checks that the disc is there (Disc/DATA/sys/main.dol). If it is not, it asks for the
//    player's disc image (.iso, .rvz, .wbfs, ...) with Android's file picker and unpacks it there
//    once (runtime/src/platform/android_disc.cpp, with nod); then it starts the game
//    (GameActivity).
//
// The app's folder is the one Android gives every app on the shared storage:
//   Android/data/io.github.hmaprecomp.animalparade/files
// A computer sees it over USB; a disc folder unpacked on a computer (Disc/DATA) can also be copied
// there instead of choosing the image.
//
// Lo primero que muestra la app: desempaca los archivos del juego, escribe la configuración la
// primera vez, revisa que el disco esté en la carpeta de la app y arranca el juego. Si falta el
// disco, pide la imagen del disco con el selector de archivos de Android y la desempaca una vez.

package io.github.hmaprecomp.animalparade;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class SetupActivity extends Activity {
    static final String GAME_FOLDER = "Game";
    private static final String ASSET_ROOT = "game";
    private static final String VERSION_FILE = "app-version.txt";

    private static final int PICK_DISC = 1;

    private TextView mText;
    private Button mRetry;
    private Button mChooseDisc;
    private final Handler mHandler = new Handler(Looper.getMainLooper());

    // Unpacks the disc image open as `fd` into `discFolder`/DATA (in libmain.so). Returns null when
    // it worked, otherwise what went wrong. nativeExtractProgress is how far it is, per thousand.
    private static native String nativeExtractDisc(int fd, String discFolder);
    private static native int nativeExtractProgress();

    // The app's own folder on the shared storage, or null while that storage is not available.
    static File dataRoot(Context context) {
        return context.getExternalFilesDir(null);
    }

    private static boolean spanish() {
        return "es".equals(Locale.getDefault().getLanguage());
    }

    private static String say(String english, String spanish) {
        return spanish() ? spanish : english;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        int padding = (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 24, getResources().getDisplayMetrics());
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(padding, padding, padding, padding);
        layout.setBackgroundColor(Color.rgb(32, 40, 24));
        mText = new TextView(this);
        mText.setTextColor(Color.WHITE);
        mText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        mText.setTextIsSelectable(true);
        mRetry = new Button(this);
        mRetry.setText(say("Try again", "Reintentar"));
        mRetry.setVisibility(Button.GONE);
        mRetry.setOnClickListener(new android.view.View.OnClickListener() {
            @Override
            public void onClick(android.view.View view) {
                prepare();
            }
        });
        mChooseDisc = new Button(this);
        mChooseDisc.setText(say("Choose your disc image", "Elegir la imagen de tu disco"));
        mChooseDisc.setVisibility(Button.GONE);
        mChooseDisc.setOnClickListener(new android.view.View.OnClickListener() {
            @Override
            public void onClick(android.view.View view) {
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("*/*");
                startActivityForResult(pick, PICK_DISC);
            }
        });
        layout.addView(mText);
        layout.addView(mChooseDisc);
        layout.addView(mRetry);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(layout);
        setContentView(scroll);
        prepare();
    }

    private void prepare() {
        mRetry.setVisibility(Button.GONE);
        mChooseDisc.setVisibility(Button.GONE);
        mText.setGravity(Gravity.CENTER);
        mText.setText(say("Getting the game ready…", "Preparando el juego…"));
        final SetupActivity activity = this;
        new Thread(new Runnable() {
            @Override
            public void run() {
                final File root = dataRoot(activity);
                String problem = null;
                if (root == null) {
                    problem = say("The shared storage is not available right now.",
                                  "El almacenamiento compartido no está disponible ahora.");
                } else {
                    try {
                        unpackGameFiles(root);
                        writeFirstSettings(root);
                    } catch (IOException e) {
                        problem = say("The game's files could not be unpacked: ", "No se pudieron desempacar los archivos del juego: ")
                                + e.getMessage();
                    }
                }
                final String error = problem;
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (error != null) {
                            showProblem(error);
                        } else if (!discFile(root).isFile()) {
                            showDiscHelp(root);
                        } else {
                            startActivity(new Intent(activity, GameActivity.class));
                            finish();
                        }
                    }
                });
            }
        }).start();
    }

    private static File discFile(File root) {
        return new File(root, "Disc/DATA/sys/main.dol");
    }

    private void showProblem(String text) {
        mText.setGravity(Gravity.START);
        mText.setText(text);
        mRetry.setVisibility(Button.VISIBLE);
    }

    private void showDiscHelp(File root) {
        showProblem(say(
            "The game needs your disc: Harvest Moon: Animal Parade for Wii, the USA release (RBIEE9), "
            + "as the image Dolphin plays (.iso, .rvz, .wbfs, .wia or .ciso).\n\n"
            + "Choose it below. The app unpacks it once to its own folder (about 5 GB, a few minutes); "
            + "the image itself can be deleted afterwards.",
            "El juego necesita tu disco: Harvest Moon: Animal Parade de Wii, la versión de Estados Unidos "
            + "(RBIEE9), como la imagen que juegas en Dolphin (.iso, .rvz, .wbfs, .wia o .ciso).\n\n"
            + "Elígela abajo. La app la desempaca una vez a su propia carpeta (unos 5 GB, unos minutos); "
            + "después puedes borrar la imagen."));
        mChooseDisc.setVisibility(Button.VISIBLE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_DISC || resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }
        final File root = dataRoot(this);
        final Uri uri = data.getData();
        final int fd;
        try {
            ParcelFileDescriptor file = getContentResolver().openFileDescriptor(uri, "r");
            if (file == null) {
                throw new IOException("no file");
            }
            fd = file.detachFd();
        } catch (IOException | SecurityException e) {
            showProblem(say("The disc image could not be opened: ", "No se pudo abrir la imagen del disco: ") + e.getMessage());
            mChooseDisc.setVisibility(Button.VISIBLE);
            return;
        }
        System.loadLibrary("main");
        mChooseDisc.setVisibility(Button.GONE);
        mRetry.setVisibility(Button.GONE);
        mText.setGravity(Gravity.CENTER);
        final Runnable progress = new Runnable() {
            @Override
            public void run() {
                int perThousand = nativeExtractProgress();
                mText.setText(say("Unpacking your disc… ", "Desempacando tu disco… ") + (perThousand / 10) + " %");
                mHandler.postDelayed(this, 500);
            }
        };
        mHandler.post(progress);
        final SetupActivity activity = this;
        new Thread(new Runnable() {
            @Override
            public void run() {
                final String error = nativeExtractDisc(fd, new File(root, "Disc").getAbsolutePath());
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        mHandler.removeCallbacks(progress);
                        if (error != null) {
                            showProblem(error);
                            mChooseDisc.setVisibility(Button.VISIBLE);
                        } else {
                            prepare();
                        }
                    }
                });
            }
        }).start();
    }

    // assets/game -> Game/, when the app's version differs from the one unpacked there.
    private void unpackGameFiles(File root) throws IOException {
        File game = new File(root, GAME_FOLDER);
        // The version, and when this copy of the app was installed: a rebuilt app of the same
        // version still unpacks its files again.
        long code = 0;
        try {
            code = getPackageManager().getPackageInfo(getPackageName(), 0).getLongVersionCode();
        } catch (android.content.pm.PackageManager.NameNotFoundException e) {
            // Not possible for the app itself.
        }
        String version = code + " " + new File(getApplicationInfo().sourceDir).lastModified();
        File stamp = new File(game, VERSION_FILE);
        if (stamp.isFile() && version.equals(readText(stamp))) {
            return;
        }
        deleteTree(game);
        copyAssets(getAssets(), ASSET_ROOT, game);
        writeText(stamp, version);
    }

    private static void copyAssets(AssetManager assets, String path, File to) throws IOException {
        String[] children = assets.list(path);
        if (children != null && children.length > 0) {
            if (!to.isDirectory() && !to.mkdirs()) {
                throw new IOException("cannot make " + to);
            }
            for (String child : children) {
                copyAssets(assets, path + "/" + child, new File(to, child));
            }
            return;
        }
        try (InputStream in = assets.open(path); OutputStream out = new FileOutputStream(to)) {
            byte[] buffer = new byte[1 << 16];
            int read;
            while ((read = in.read(buffer)) > 0) {
                out.write(buffer, 0, read);
            }
        }
    }

    // portable.txt, and Config.toml with the disc's folder the first time.
    private static void writeFirstSettings(File root) throws IOException {
        File portable = new File(root, "portable.txt");
        if (!portable.isFile()) {
            writeText(portable, "Harvest Moon: Animal Parade keeps its user data in UserData.\n");
        }
        File config = new File(root, "UserData/Config.toml");
        if (!config.isFile()) {
            String disc = new File(root, "Disc/DATA").getAbsolutePath().replace("\\", "\\\\").replace("\"", "\\\"");
            writeText(config, "[paths]\ndvd_root = \"" + disc + "\"\n");
        }
    }

    private static String readText(File file) throws IOException {
        try (InputStream in = new java.io.FileInputStream(file)) {
            byte[] bytes = new byte[(int) file.length()];
            int at = 0;
            while (at < bytes.length) {
                int read = in.read(bytes, at, bytes.length - at);
                if (read < 0) break;
                at += read;
            }
            return new String(bytes, 0, at, StandardCharsets.UTF_8);
        }
    }

    private static void writeText(File file, String text) throws IOException {
        File parent = file.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("cannot make " + parent);
        }
        try (OutputStream out = new FileOutputStream(file)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }

    private static void deleteTree(File file) {
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) {
                deleteTree(child);
            }
        }
        file.delete();
    }
}
