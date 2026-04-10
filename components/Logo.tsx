import Image from "next/image";
import Link from "next/link";

export default function Logo({ small = false }: { small?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2">
      <Image
        src={small ? "/vocalorie-icon.png" : "/vocalorie-logo.png"}
        alt="Vocalorie"
        width={small ? 42 : 180}
        height={small ? 42 : 60}
        priority
      />
    </Link>
  );
}