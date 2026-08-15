import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PatientCapital — спокойный план для капитала",
  description:
    "Локальный инвестиционный журнал с воспроизводимым планом пополнений и прозрачной аналитикой.",
  openGraph: {
    title: "PatientCapital",
    description: "Спокойный, воспроизводимый план для долгосрочного капитала.",
    type: "website",
    locale: "ru_RU",
    images: [
      {
        url: "/patientcapital-social.png",
        width: 1536,
        height: 1024,
        alt: "PatientCapital — долгосрочный инвестиционный план",
      },
    ],
  },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#153c34",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
