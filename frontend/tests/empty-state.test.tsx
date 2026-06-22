import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/app/components/feedback/FeedbackStates";

describe("EmptyState", () => {
  it("menampilkan title dan description analytics empty state", () => {
    render(<EmptyState title="Belum Ada Data" description="Upload CSV untuk melihat analytics." />);
    expect(screen.getByText("Belum Ada Data")).toBeInTheDocument();
    expect(screen.getByText("Upload CSV untuk melihat analytics.")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("menampilkan error backend tidak tersedia", () => {
    render(<ErrorState message="Backend tidak dapat dihubungi." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Backend tidak dapat dihubungi.");
  });
});

describe("LoadingSkeleton", () => {
  it("memiliki atribut aria-busy saat loading", () => {
    render(<LoadingSkeleton lines={3} />);
    expect(screen.getByLabelText("Memuat data")).toHaveAttribute("aria-busy", "true");
  });
});
