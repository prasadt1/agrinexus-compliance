/**
 * Guided tour — same interaction model as Outturn (driver.js spotlight).
 * Pages set window.COMPLIANCE_TOUR_STEPS before this script runs, or use built-ins.
 */
(function () {
  const SEEN_KEY = "agrinexus_compliance_tour_seen";
  const START_EVENT = "compliance:start-tour";

  function presentSteps(steps) {
    return (steps || []).filter(function (s) {
      if (!s.element) return true;
      if (typeof s.element !== "string") return true;
      return !!document.querySelector(s.element);
    });
  }

  function addSkipButton(popover, d) {
    if (popover.footerButtons.querySelector(".outturn-skip-btn")) return;
    const skip = document.createElement("button");
    skip.type = "button";
    skip.textContent = "Skip";
    skip.className = "driver-popover-prev-btn outturn-skip-btn";
    skip.addEventListener("click", function () {
      d.destroy();
    });
    popover.footerButtons.insertBefore(skip, popover.nextButton);
  }

  const PAGE_STEPS = {
    check: [
      {
        popover: {
          title: "Welcome — ESA label check",
          description:
            "This demo helps an applicator check Endangered Species Act pesticide-label steps for one field and product, then keep a dated record. Same closed-loop idea as Outturn / AgriNexus — U.S. compliance domain.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Start tour",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="welcome"]',
        popover: {
          title: "What you are looking at",
          description:
            "A guided educational demo for extension and pesticide-safety educators — not legal advice. The product label always controls.",
        },
      },
      {
        element: '[data-tour="summary"]',
        popover: {
          title: "Real demo pack",
          description:
            "Boone County, Iowa + Liberty ULTRA (EPA Reg. No. 7969-500) + August 2026 Bulletins Live! Two printable. Mitigation points match the Iowa State ICM table example.",
        },
      },
      {
        element: '[data-tour="check-cta"]',
        popover: {
          title: "Check the application",
          description:
            "One click scores mitigation points and weather against the label. After the tour, press this button to see a live verdict.",
        },
      },
      {
        element: '[data-tour="honesty-preview"]',
        popover: {
          title: "Honesty split",
          description:
            "Blue = calculated from published rules (points, weather). Green = optional AI reading. Rules never pretend to be AI.",
        },
      },
      {
        element: '[data-tour="steps"]',
        popover: {
          title: "Three steps",
          description:
            "Check → Confirm (reminders + free-text) → Record (downloadable PDF). That loop is the product.",
        },
      },
    ],
    confirm: [
      {
        popover: {
          title: "Confirm what was done",
          description:
            "After the plan, the applicator describes what they completed in their own words. Reminders (T+24 / T+48) are the follow-through loop — same idea as Outturn.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="case-summary"]',
        popover: {
          title: "This application",
          description: "Field, product, and plan result for the case you just opened.",
        },
      },
      {
        element: '[data-tour="timeline"]',
        popover: {
          title: "Activity timeline",
          description:
            "Plan created, simulated reminders, confirmation — all land on the receipt.",
        },
      },
      {
        element: '[data-tour="confirm-form"]',
        popover: {
          title: "Free-text confirmation",
          description:
            "Not a keyword DONE button. Describe bulletin, practices, and spray conditions in plain language.",
        },
      },
    ],
    receipt: [
      {
        popover: {
          title: "Application record",
          description:
            "The artifact an educator can keep or email: points, weather, reminders, confirmation, and fixture citations.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="receipt-verdict"]',
        popover: {
          title: "Status first",
          description: "Plain-language status before any technical detail.",
        },
      },
      {
        element: '[data-tour="download-pdf"]',
        popover: {
          title: "Download the PDF",
          description: "Primary action: take away a one-page educational audit record.",
        },
      },
      {
        element: '[data-tour="receipt-timeline"]',
        popover: {
          title: "Full activity trail",
          description: "Includes simulated day-1 / day-2 reminders when you used them on Confirm.",
        },
      },
    ],
  };

  function getSteps() {
    if (window.COMPLIANCE_TOUR_STEPS && window.COMPLIANCE_TOUR_STEPS.length) {
      return presentSteps(window.COMPLIANCE_TOUR_STEPS);
    }
    const page = document.body.getAttribute("data-tour-page") || "check";
    return presentSteps(PAGE_STEPS[page] || PAGE_STEPS.check);
  }

  function startTour() {
    if (!window.driver || !window.driver.js || !window.driver.js.driver) {
      console.warn("driver.js not loaded");
      return;
    }
    const steps = getSteps();
    if (!steps.length) return;
    const d = window.driver.js.driver({
      showProgress: true,
      progressText: "{{current}} of {{total}}",
      allowClose: true,
      overlayColor: "#1a1714",
      overlayOpacity: 0.55,
      stagePadding: 6,
      stageRadius: 10,
      popoverClass: "outturn-tour",
      nextBtnText: "Next",
      prevBtnText: "Back",
      doneBtnText: "Done",
      onDestroyed: function () {
        try {
          localStorage.setItem(SEEN_KEY, "1");
        } catch (e) {
          /* ignore */
        }
      },
      steps: steps,
    });
    d.drive();
  }

  window.startComplianceTour = startTour;
  window.addEventListener(START_EVENT, startTour);

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-tour-trigger]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        startTour();
      });
    });

    var auto = document.body.getAttribute("data-tour-auto");
    if (auto === "false") return;
    var seen = "0";
    try {
      seen = localStorage.getItem(SEEN_KEY) || "0";
    } catch (e) {
      seen = "1";
    }
    if (seen === "1") return;
    if (window.innerWidth < 768) return;
    window.setTimeout(startTour, 700);
  });
})();
