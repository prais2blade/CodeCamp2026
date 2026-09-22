import { useQuery } from "@tanstack/react-query";

import {
    getReportSummary,
    getStudentStats
} from "../api/reportApi";
import {
    getAttendanceTrend
} from "../api/reportApi";

export const useReportSummary = () => {

    return useQuery({

        queryKey: ["report-summary"],

        queryFn: getReportSummary

    });

};

export const useStudentStats = () => {

    return useQuery({

        queryKey: ["student-stats"],

        queryFn: getStudentStats

    });

};

export const useAttendanceTrend = () => {

    return useQuery({

        queryKey: ["attendance-trend"],

        queryFn: getAttendanceTrend

    });

};