import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TagInput } from "@/components/ui/tag-input";

function Harness({ initial = [] as string[] }) {
  const [values, setValues] = useState(initial);
  return (
    <>
      <TagInput label="Skills" values={values} onChange={setValues} />
      <output data-testid="values">{JSON.stringify(values)}</output>
    </>
  );
}

const current = () => JSON.parse(screen.getByTestId("values").textContent ?? "[]") as string[];

describe("TagInput", () => {
  it("adds items with Enter and comma, ignoring duplicates", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Skills", { selector: "input" });
    await userEvent.type(input, "Python{Enter}PyTorch,python,{Enter}");
    expect(current()).toEqual(["Python", "PyTorch"]);
    expect(input).toHaveValue("");
  });

  it("splits pasted comma lists and adds on blur", async () => {
    render(<Harness />);
    const input = screen.getByLabelText("Skills", { selector: "input" });
    await userEvent.click(input);
    await userEvent.paste("SQL, dbt , Airflow");
    await userEvent.tab();
    expect(current()).toEqual(["SQL", "dbt", "Airflow"]);
  });

  it("removes items with their button and with Backspace", async () => {
    render(<Harness initial={["Python", "SQL", "Go"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove SQL" }));
    expect(current()).toEqual(["Python", "Go"]);
    await userEvent.type(screen.getByLabelText("Skills", { selector: "input" }), "{Backspace}");
    expect(current()).toEqual(["Python"]);
  });
});
