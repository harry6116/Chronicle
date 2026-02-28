# Chronicle: Processing Examples

This document demonstrates Chronicle's ability to reconstruct complex, non-linear historical documents into accessible, structured data. 

**Source Material:** *Newcastle Morning Herald and Miners' Advocate*, Saturday, 15 November 1947.
[View Original on Trove (National Library of Australia)](https://trove.nla.gov.au/newspaper/article/134243010)

---

## Example 1: Visual Comic Strip Scripting

Standard OCR and extraction tools typically fail on comic strips, treating them as unreadable noise or a jumble of disconnected words. Chronicle analyzes the visual sequence and scripts the action for screen reader users.

### The Problem (Standard Extraction)
> Mutt See that window washer? I'll bet him I can guess the date on a coin in his pocket! Jeff You'll lose! How can you? Go ahead. 1947! How'd you know? That's what year it is, isn't it? He'd have some coin of this year's date in his pocket!

### The Chronicle Solution
Chronicle reconstructs the comic "Mutt and Jeff" as a linear narrative:
> **Panel 1:** Mutt, the tall character, points up at a man washing a high window. He says to the short character, Jeff, "See that window washer? I'll bet him I can guess the date on a coin in his pocket!"
> **Panel 2:** Mutt cups his hands and yells to the window washer, "I'll bet you a dollar I can tell you the date on a coin in your pocket!"
> **Panel 3:** The window washer replies, "Go ahead." Mutt shouts back, "1947!" 
> **Panel 4:** Jeff asks, "How'd you know?" Mutt replies, "That's what year it is, isn't it? He'd have some coin of this year's date in his pocket!"

---

## Example 2: Structural Table Reconstruction

The "New Lambton Bowls Pennant Teams" section in this issue is a dense grid of names and numbers. Most tools fail to maintain the row/column relationship, making the data incomprehensible for VoiceOver users.

### The Problem (Standard Extraction)
> No. 1 Grade v. Hamilton Park at New Lambton: (1) J. Rees C. Johns F. Jarman J. Miller (s) (2) J. Gibson C. Hughes F. O'Hearn L. Graham (s) (3) W. Graham W. Rees G. Graham D. Rees (s)

### The Chronicle Solution
Chronicle identifies the tabular data and outputs a valid HTML table. This allows a VoiceOver user to navigate by column (e.g., "Who is the skip for Rink 2?") instead of hearing a "word salad" of names.

| Grade | Rink | Players |
| :--- | :--- | :--- |
| No. 1 v. Hamilton Park | 1 | J. Rees, C. Johns, F. Jarman, J. Miller (s) |
| No. 1 v. Hamilton Park | 2 | J. Gibson, C. Hughes, F. O'Hearn, L. Graham (s) |
| No. 1 v. Hamilton Park | 3 | W. Graham, W. Rees, G. Graham, D. Rees (s) |

---

## Example 3: Layout Flattening (Catherine Hill Bay)

Historical newsprint uses multi-column layouts that "snake" around advertisements. Standard tools read straight across the page, mixing the story with ads.

### The Chronicle Solution
Chronicle ignores the visual layout noise to extract a clean, linear narrative:
> **Heading:** "Second Minmi" Wants Better Deal
> **Narrative:** Residents of Catherine Hill Bay fear the settlement is deteriorating into a "second Minmi" unless they are given a better deal! The fear was expressed this week by the President of the Progress Association (Mr. A. P. Doyle)...

Chronicle also generates detailed descriptions for accompanying archival photographs, such as the image of Jeanette and Patricia Simpson walking through the mining village, which is otherwise entirely invisible to blind researchers.
