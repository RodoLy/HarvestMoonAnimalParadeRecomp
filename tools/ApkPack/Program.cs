// ApkPack: makes the Android app from the shell the project ships and the game the player's
// computer compiled.
//
//   ApkPack --shell AnimalParade-shell.apk --lib arm64-v8a=libmain.so --assets Game
//           --key UserData/android-signing.pfx --out AnimalParade.apk
//
// 1. Copies the shell's files (the manifest, the Java code, the icon), as they are.
// 2. Adds the game as lib/<abi>/libmain.so and every file under --assets as assets/game/...
//    (dsp_coef.bin, wii_bootstrap, ...; the app unpacks them on the device).
// 3. Signs the app with APK Signature Scheme v2, the one Android 11 and later check. The key is
//    made the first time and kept (--key), so a later build installs over the earlier one and
//    keeps its saves. It is the player's own key, never shared.
//
// Nothing here needs Java or the Android SDK: the zip file is written by hand, so the files that
// Android reads in place are aligned as it wants them.
//
// ApkPack: arma la app de Android con el cascarón del proyecto y el juego que compiló la
// computadora del jugador, y la firma (esquema v2) con una llave propia que se guarda para que
// las versiones siguientes se instalen encima.

using System.Buffers.Binary;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;

namespace ApkPack;

static class Program {
    static int Main(string[] args) {
        try {
            var options = Options.Parse(args);
            if (options is null) {
                Console.Error.WriteLine(Options.Usage);
                return 2;
            }
            Run(options);
            return 0;
        } catch (Exception e) when (e is IOException or InvalidDataException or CryptographicException or ArgumentException) {
            Console.Error.WriteLine("ApkPack: " + e.Message);
            if (Environment.GetEnvironmentVariable("APKPACK_DEBUG") is not null) Console.Error.WriteLine(e);
            return 1;
        }
    }

    static void Run(Options options) {
        var shell = Zip.Read(options.Shell);
        var entries = new List<ZipEntry>();
        foreach (var entry in shell) {
            // Old signatures, and anything this run puts in itself.
            if (entry.Name.StartsWith("META-INF/", StringComparison.Ordinal) ||
                entry.Name.StartsWith("lib/", StringComparison.Ordinal) ||
                entry.Name.StartsWith("assets/game/", StringComparison.Ordinal)) {
                continue;
            }
            entries.Add(entry);
        }
        foreach (var (abi, path) in options.Libraries) {
            Console.WriteLine($"ApkPack: adding {Path.GetFileName(path)} for {abi}");
            entries.Add(ZipEntry.Compress($"lib/{abi}/{Path.GetFileName(path)}", File.ReadAllBytes(path)));
        }
        if (options.Assets is not null) {
            var root = Path.GetFullPath(options.Assets);
            var files = Directory.GetFiles(root, "*", SearchOption.AllDirectories);
            Array.Sort(files, StringComparer.Ordinal);
            foreach (var file in files) {
                var relative = Path.GetRelativePath(root, file).Replace('\\', '/');
                entries.Add(ZipEntry.Compress("assets/game/" + relative, File.ReadAllBytes(file)));
            }
            Console.WriteLine($"ApkPack: adding {files.Length} game file(s) from {root}");
        }

        var unsigned = Zip.Write(entries);
        using var certificate = SigningKey.LoadOrCreate(options.Key);
        var signed = SignatureV2.Sign(unsigned, certificate);
        var output = Path.GetFullPath(options.Output);
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        File.WriteAllBytes(output + ".part", signed);
        File.Move(output + ".part", output, overwrite: true);
        Console.WriteLine($"ApkPack: wrote {output} ({signed.Length / (1024 * 1024)} MB)");
    }
}

sealed class Options {
    public const string Usage =
        "Usage: ApkPack --shell SHELL.apk --out OUT.apk --key KEY.pfx [--lib ABI=FILE.so]... [--assets DIR]";

    public string Shell = "";
    public string Output = "";
    public string Key = "";
    public string? Assets;
    public List<(string Abi, string Path)> Libraries = new();

    public static Options? Parse(string[] args) {
        var options = new Options();
        for (int i = 0; i < args.Length; ++i) {
            string Next() => i + 1 < args.Length ? args[++i] : throw new ArgumentException($"{args[i]} needs a value");
            switch (args[i]) {
            case "--shell": options.Shell = Next(); break;
            case "--out": options.Output = Next(); break;
            case "--key": options.Key = Next(); break;
            case "--assets": options.Assets = Next(); break;
            case "--lib": {
                var value = Next();
                int equals = value.IndexOf('=');
                if (equals <= 0) throw new ArgumentException("--lib takes ABI=FILE, like arm64-v8a=libmain.so");
                options.Libraries.Add((value[..equals], value[(equals + 1)..]));
                break;
            }
            case "-h":
            case "--help":
                return null;
            default:
                throw new ArgumentException($"unknown argument {args[i]}");
            }
        }
        if (options.Shell.Length == 0 || options.Output.Length == 0 || options.Key.Length == 0) return null;
        return options;
    }
}

// One file in the zip: its name, how it is stored, and its data as stored.
sealed class ZipEntry {
    public const ushort Stored = 0, Deflated = 8;
    public required string Name;
    public ushort Method;
    public uint Crc;
    public uint UncompressedSize;
    public required byte[] Data;   // as stored (compressed for Deflated)

    public static ZipEntry Compress(string name, byte[] content) {
        using var buffer = new MemoryStream();
        using (var deflate = new DeflateStream(buffer, CompressionLevel.Optimal, leaveOpen: true)) {
            deflate.Write(content);
        }
        return new ZipEntry {
            Name = name,
            Method = Deflated,
            Crc = Crc32.Of(content),
            UncompressedSize = (uint)content.Length,
            Data = buffer.ToArray(),
        };
    }
}

static class Crc32 {
    static readonly uint[] Table = Enumerable.Range(0, 256).Select(n => {
        uint c = (uint)n;
        for (int k = 0; k < 8; ++k) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        return c;
    }).ToArray();

    public static uint Of(ReadOnlySpan<byte> data) {
        uint crc = 0xFFFFFFFFu;
        foreach (byte b in data) crc = Table[(crc ^ b) & 0xFF] ^ (crc >> 8);
        return crc ^ 0xFFFFFFFFu;
    }
}

static class Zip {
    const uint LocalHeader = 0x04034b50, CentralHeader = 0x02014b50, EndOfCentral = 0x06054b50;
    // Files Android reads straight from the app (resources.arsc, anything stored) start on a
    // multiple of 4 bytes, as zipalign leaves them; shared libraries stored as they are would
    // need a page, but the game's are compressed and unpacked on install.
    const int StoredAlignment = 4;
    const int LibraryAlignment = 16384;
    // zipalign's extra field that holds the padding.
    const ushort AlignmentExtraId = 0xD935;
    // 1 January 1981, 00:00: a fixed time keeps the same build byte for byte the same.
    const ushort DosTime = 0, DosDate = (1 << 9) | (1 << 5) | 1;

    public static List<ZipEntry> Read(string path) {
        var bytes = File.ReadAllBytes(path);
        int end = -1;
        for (int i = bytes.Length - 22; i >= Math.Max(0, bytes.Length - 22 - 65535); --i) {
            if (BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(i)) == EndOfCentral) { end = i; break; }
        }
        if (end < 0) throw new InvalidDataException($"{path} is not a zip file");
        int count = BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(end + 10));
        int at = (int)BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(end + 16));
        var entries = new List<ZipEntry>();
        for (int n = 0; n < count; ++n) {
            var header = bytes.AsSpan(at);
            if (BinaryPrimitives.ReadUInt32LittleEndian(header) != CentralHeader) throw new InvalidDataException($"{path}: bad central directory");
            ushort method = BinaryPrimitives.ReadUInt16LittleEndian(header[10..]);
            uint crc = BinaryPrimitives.ReadUInt32LittleEndian(header[16..]);
            uint compressed = BinaryPrimitives.ReadUInt32LittleEndian(header[20..]);
            uint size = BinaryPrimitives.ReadUInt32LittleEndian(header[24..]);
            int nameLength = BinaryPrimitives.ReadUInt16LittleEndian(header[28..]);
            int extraLength = BinaryPrimitives.ReadUInt16LittleEndian(header[30..]);
            int commentLength = BinaryPrimitives.ReadUInt16LittleEndian(header[32..]);
            int local = (int)BinaryPrimitives.ReadUInt32LittleEndian(header[42..]);
            string name = Encoding.UTF8.GetString(header.Slice(46, nameLength));
            var localHeader = bytes.AsSpan(local);
            if (BinaryPrimitives.ReadUInt32LittleEndian(localHeader) != LocalHeader) throw new InvalidDataException($"{path}: bad entry {name}");
            int data = local + 30 + BinaryPrimitives.ReadUInt16LittleEndian(localHeader[26..]) + BinaryPrimitives.ReadUInt16LittleEndian(localHeader[28..]);
            if (method != ZipEntry.Stored && method != ZipEntry.Deflated) throw new InvalidDataException($"{path}: {name} uses compression method {method}");
            entries.Add(new ZipEntry {
                Name = name, Method = method, Crc = crc, UncompressedSize = size,
                Data = bytes.AsSpan(data, (int)compressed).ToArray(),
            });
            at += 46 + nameLength + extraLength + commentLength;
        }
        return entries;
    }

    public static byte[] Write(List<ZipEntry> entries) {
        using var output = new MemoryStream();
        var central = new MemoryStream();
        foreach (var entry in entries) {
            var name = Encoding.UTF8.GetBytes(entry.Name);
            long offset = output.Position;
            if (offset > uint.MaxValue) throw new InvalidDataException("the app would be over 4 GB");
            byte[] extra = Array.Empty<byte>();
            if (entry.Method == ZipEntry.Stored) {
                int alignment = entry.Name.EndsWith(".so", StringComparison.Ordinal) ? LibraryAlignment : StoredAlignment;
                long dataStart = offset + 30 + name.Length;
                int padding = (int)((alignment - dataStart % alignment) % alignment);
                while (padding < 6) padding += alignment;   // the extra field's own header is 6 bytes
                extra = new byte[padding];
                BinaryPrimitives.WriteUInt16LittleEndian(extra, AlignmentExtraId);
                BinaryPrimitives.WriteUInt16LittleEndian(extra.AsSpan(2), (ushort)(padding - 4));
                BinaryPrimitives.WriteUInt16LittleEndian(extra.AsSpan(4), (ushort)alignment);
            }
            var local = new byte[30];
            BinaryPrimitives.WriteUInt32LittleEndian(local, LocalHeader);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(4), 20);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(6), 1 << 11);   // UTF-8 names
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(8), entry.Method);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(10), DosTime);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(12), DosDate);
            BinaryPrimitives.WriteUInt32LittleEndian(local.AsSpan(14), entry.Crc);
            BinaryPrimitives.WriteUInt32LittleEndian(local.AsSpan(18), (uint)entry.Data.Length);
            BinaryPrimitives.WriteUInt32LittleEndian(local.AsSpan(22), entry.UncompressedSize);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(26), (ushort)name.Length);
            BinaryPrimitives.WriteUInt16LittleEndian(local.AsSpan(28), (ushort)extra.Length);
            output.Write(local);
            output.Write(name);
            output.Write(extra);
            output.Write(entry.Data);

            var header = new byte[46];
            BinaryPrimitives.WriteUInt32LittleEndian(header, CentralHeader);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(4), 20);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(6), 20);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(8), 1 << 11);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(10), entry.Method);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(12), DosTime);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(14), DosDate);
            BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(16), entry.Crc);
            BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(20), (uint)entry.Data.Length);
            BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(24), entry.UncompressedSize);
            BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(28), (ushort)name.Length);
            BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(42), (uint)offset);
            central.Write(header);
            central.Write(name);
        }
        long centralOffset = output.Position;
        central.Position = 0;
        central.CopyTo(output);
        var end = new byte[22];
        BinaryPrimitives.WriteUInt32LittleEndian(end, EndOfCentral);
        BinaryPrimitives.WriteUInt16LittleEndian(end.AsSpan(8), (ushort)entries.Count);
        BinaryPrimitives.WriteUInt16LittleEndian(end.AsSpan(10), (ushort)entries.Count);
        BinaryPrimitives.WriteUInt32LittleEndian(end.AsSpan(12), (uint)central.Length);
        BinaryPrimitives.WriteUInt32LittleEndian(end.AsSpan(16), (uint)centralOffset);
        output.Write(end);
        if (entries.Count > ushort.MaxValue || output.Length > uint.MaxValue) throw new InvalidDataException("the app is too large for a zip file without zip64");
        return output.ToArray();
    }
}

static class SigningKey {
    const string Password = "animal-parade-local";

    // The player's own signing key: made once, then kept beside their settings.
    public static X509Certificate2 LoadOrCreate(string path) {
        if (File.Exists(path)) {
            return new X509Certificate2(path, Password, X509KeyStorageFlags.Exportable | X509KeyStorageFlags.EphemeralKeySet);
        }
        Console.WriteLine($"ApkPack: making a signing key at {path} (keep it: the next build signs with it too)");
        using var rsa = RSA.Create(2048);
        var request = new CertificateRequest("CN=Animal Parade (built on this computer)", rsa, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        var now = DateTimeOffset.UtcNow;
        using var made = request.CreateSelfSigned(now.AddDays(-1), now.AddYears(50));
        var pfx = made.Export(X509ContentType.Pfx, Password);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        File.WriteAllBytes(path, pfx);
        return new X509Certificate2(pfx, Password, X509KeyStorageFlags.Exportable | X509KeyStorageFlags.EphemeralKeySet);
    }
}

// APK Signature Scheme v2 (source.android.com/docs/security/features/apksigning/v2): a block
// between the files and the zip's central directory that signs a digest of everything else.
static class SignatureV2 {
    const uint BlockId = 0x7109871a;
    const uint RsaPkcs1Sha256 = 0x0103;
    const int ChunkSize = 1024 * 1024;

    public static byte[] Sign(byte[] zip, X509Certificate2 certificate) {
        int end = zip.Length - 22;   // Zip.Write leaves no comment
        if (BinaryPrimitives.ReadUInt32LittleEndian(zip.AsSpan(end)) != 0x06054b50) throw new InvalidDataException("no end of central directory");
        int centralOffset = (int)BinaryPrimitives.ReadUInt32LittleEndian(zip.AsSpan(end + 16));

        var digest = Digest(zip.AsMemory(0, centralOffset), zip.AsMemory(centralOffset, end - centralOffset), zip.AsMemory(end));
        var digests = Prefixed(Prefixed(Concat(U32(RsaPkcs1Sha256), Prefixed(digest))));
        var certificates = Prefixed(Prefixed(certificate.RawData));
        var attributes = Prefixed(Array.Empty<byte>());
        var signedData = Concat(digests, certificates, attributes);

        using var key = certificate.GetRSAPrivateKey() ?? throw new CryptographicException("the signing key has no RSA private key");
        var signature = key.SignData(signedData, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        using var publicKey = certificate.GetRSAPublicKey()!;
        var signer = Concat(
            Prefixed(signedData),
            Prefixed(Prefixed(Concat(U32(RsaPkcs1Sha256), Prefixed(signature)))),
            Prefixed(publicKey.ExportSubjectPublicKeyInfo()));
        var value = Prefixed(Prefixed(signer));

        var pair = Concat(U64((ulong)(4 + value.Length)), U32(BlockId), value);
        ulong blockSize = (ulong)pair.Length + 8 + 16;
        var block = Concat(U64(blockSize), pair, U64(blockSize), Encoding.ASCII.GetBytes("APK Sig Block 42"));

        var signed = new byte[zip.Length + block.Length];
        zip.AsSpan(0, centralOffset).CopyTo(signed);
        block.CopyTo(signed, centralOffset);
        zip.AsSpan(centralOffset).CopyTo(signed.AsSpan(centralOffset + block.Length));
        BinaryPrimitives.WriteUInt32LittleEndian(signed.AsSpan(end + block.Length + 16), (uint)(centralOffset + block.Length));
        return signed;
    }

    // SHA-256 over 1 MB chunks of the three parts, then over the chunks' digests.
    static byte[] Digest(params ReadOnlyMemory<byte>[] parts) {
        var chunkDigests = new List<byte[]>();
        foreach (var part in parts) {
            for (int at = 0; at < part.Length; at += ChunkSize) {
                var chunk = part.Span.Slice(at, Math.Min(ChunkSize, part.Length - at));
                using var sha = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                sha.AppendData(new byte[] { 0xa5 });
                sha.AppendData(U32((uint)chunk.Length));
                sha.AppendData(chunk);
                chunkDigests.Add(sha.GetHashAndReset());
            }
        }
        using var top = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        top.AppendData(new byte[] { 0x5a });
        top.AppendData(U32((uint)chunkDigests.Count));
        foreach (var d in chunkDigests) top.AppendData(d);
        return top.GetHashAndReset();
    }

    static byte[] U32(uint value) {
        var bytes = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(bytes, value);
        return bytes;
    }

    static byte[] U64(ulong value) {
        var bytes = new byte[8];
        BinaryPrimitives.WriteUInt64LittleEndian(bytes, value);
        return bytes;
    }

    static byte[] Prefixed(byte[] data) => Concat(U32((uint)data.Length), data);

    static byte[] Concat(params byte[][] parts) {
        var all = new byte[parts.Sum(p => p.Length)];
        int at = 0;
        foreach (var part in parts) {
            part.CopyTo(all, at);
            at += part.Length;
        }
        return all;
    }
}
