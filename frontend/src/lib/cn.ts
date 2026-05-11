import clsx, { type ClassValue } from "clsx";

/** Small className helper used by every component for conditional class joining. */
export const cn = (...inputs: ClassValue[]): string => clsx(...inputs);
